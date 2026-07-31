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
        # Affordances preserved
        self.assertIn("suite-free-grid", main)
        self.assertIn("/suite/download?platform=windows", main)
        self.assertIn("dl-buy-now", main)
        self.assertIn("KEYGEN", main)

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
            # Dual shop is first content after header (intro after shop)
            self.assertLess(i_row, i_intro)
        i_nw = main.find("node-wipe")
        if i_nw > 0:
            self.assertLess(i_row, i_nw)


if __name__ == "__main__":
    unittest.main()
