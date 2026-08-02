"""Homepage Suite + downloads boxes: side-by-side halves at top of main content."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


def _main_html(page: str) -> str:
    """Body main content only (skip CSS that reuses class names)."""
    i = page.find('id="page-shell"')
    if i < 0:
        i = page.find("<body")
    return page[i:] if i >= 0 else page


class TestHomepageTwoHalves(unittest.TestCase):
    def test_intro_above_shop_row(self) -> None:
        from app import render_html

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = _main_html(page)
        self.assertIn("...privacy you can actually use...", main)
        self.assertIn(".:WELCOME, ANON:.", main)
        self.assertIn("suite-home-intro", main)
        i_header = main.index('id="brand-panel"')
        i_intro = main.index("suite-home-intro")
        i_row = main.index('id="home-shop-row"')
        i_suite = main.index('id="suite-storefront"')
        i_dl = main.index('id="downloads"')
        self.assertLess(i_header, i_intro)
        self.assertLess(i_intro, i_row)
        self.assertLess(i_row, i_suite)
        self.assertLess(i_suite, i_dl)

    def test_shop_row_side_by_side_css_and_structure(self) -> None:
        from app import render_html

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = _main_html(page)
        self.assertIn('id="home-shop-row"', main)
        self.assertIn('data-home-shop-row="1"', main)
        self.assertIn('data-layout="two-halves"', main)
        self.assertIn('id="suite-storefront"', main)
        self.assertIn('id="downloads"', main)
        # Side-by-side grid in page CSS
        self.assertIn(".home-shop-row", page)
        self.assertIn("grid-template-columns: 1fr 1fr", page)
        self.assertIn("@media (max-width: 820px)", page)
        i_row = main.index('id="home-shop-row"')
        i_suite = main.index('id="suite-storefront"')
        i_dl = main.index('id="downloads"')
        self.assertLess(i_row, i_suite)
        self.assertLess(i_suite, i_dl)
        # Bottom sections after shop row
        for marker in ("audit-panel", "node-wipe"):
            j = main.find(marker)
            if j >= 0:
                self.assertLess(i_dl, j, f"{marker} must follow downloads in main")
        # Affordances: KEYGEN cart entry + free CTA (no Device-for-KEYGEN / package grid)
        self.assertNotIn('id="suite-free-grid"', main)
        self.assertNotIn("Device for KEYGEN", main)
        self.assertIn("suite-keygen-buy", main)
        self.assertIn('action="/pay"', main)
        self.assertIn("dl-buy-now", main)
        self.assertIn("KEYGEN", main)
        # With detected platform, free CTA is direct Suite download (not /pay)
        page_win = render_html(
            {"title": "RESTORE PRIVACY"}, default_platform="windows"
        ).decode("utf-8")
        main_win = _main_html(page_win)
        self.assertIn("free_direct=1", main_win)
        self.assertIn("/suite/download?platform=windows", main_win)
        self.assertNotIn('id="suite-free-grid"', main_win)
        self.assertNotIn("Device for KEYGEN", main_win)
        i_cta = main_win.index('id="free-download-v1-cta"')
        cta_snip = main_win[i_cta : i_cta + 700]
        self.assertIn("free_direct=1", cta_snip)
        self.assertNotIn("/pay", cta_snip)

    def test_shop_row_order_after_header_before_bottom_sections(self) -> None:
        from app import render_html

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = _main_html(page)
        i_header = main.index('id="brand-panel"')
        i_row = main.index('id="home-shop-row"')
        i_audit = main.index("audit-panel")
        self.assertLess(i_header, i_row)
        self.assertLess(i_row, i_audit)
        i_intro = main.find("suite-home-intro")
        if i_intro > 0:
            # Intro (welcome typewriter + tagline) sits above dual shop row
            self.assertLess(i_header, i_intro)
            self.assertLess(i_intro, i_row)
        i_nw = main.find("node-wipe")
        if i_nw > 0:
            self.assertLess(i_row, i_nw)
        # Full business package box is not mounted on the homepage.
        self.assertNotIn('id="download-node-preference"', main)
        self.assertNotIn("Full business package?", main)
        self.assertNotIn("data-home-business-package", main)
        self.assertNotIn("node-pref-deposit-btn", main)
        self.assertNotIn('data-business-package="1"', main)


if __name__ == "__main__":
    unittest.main()
