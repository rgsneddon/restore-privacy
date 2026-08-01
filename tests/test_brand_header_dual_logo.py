"""Desktop dual-logo brand header: logo — banner — logo, equal size/gap."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestBrandHeaderDualLogo(unittest.TestCase):
    def test_markup_logo_banner_logo_same_src_and_height(self) -> None:
        from public_chrome import (
            PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT,
            PUBLIC_BRAND_LOGO_PATH,
            public_brand_header_html,
        )

        header = public_brand_header_html()
        self.assertIn('data-dual-logo="1"', header)
        mark = header[header.index('id="brand-mark"') : header.index("</div>", header.index('id="brand-mark"'))]
        self.assertIn("brand-logo-left", mark)
        self.assertIn("brand-banner", mark)
        self.assertIn("brand-logo-right", mark)
        i_l = mark.index("brand-logo-left")
        i_b = mark.index("brand-banner")
        i_r = mark.index("brand-logo-right")
        self.assertLess(i_l, i_b)
        self.assertLess(i_b, i_r)
        # Same logo asset both sides
        self.assertEqual(mark.count(PUBLIC_BRAND_LOGO_PATH), 2)
        # Same height on left logo, banner, right logo
        h = f'height="{PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT}"'
        self.assertEqual(header.count(h), 3)

    def test_css_symmetric_gap_and_desktop_breakpoint(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        # Shared size token for both logos
        logo_block = css[css.index(".brand-logo") : css.index(".brand-logo") + 900]
        self.assertIn("var(--rb-brand-header-height)", logo_block)
        self.assertIn("brand-logo-left", logo_block)
        self.assertIn("brand-logo-right", logo_block)
        # Equal flex gap on brand-mark
        mark_i = css.index(".brand-mark {")
        mark_css = css[mark_i : mark_i + 400]
        self.assertIn("gap:", mark_css)
        self.assertIn("column-gap:", mark_css)
        # Desktop shows dual logos
        self.assertIn("@media (min-width: 521px)", css)
        desk = css[css.index("@media (min-width: 521px)") :]
        desk = desk[: desk.find("@media (", 1) if desk.find("@media (", 1) > 0 else 1200]
        # fall back: take first 1000 chars after min-width 521
        desk = css[css.index("@media (min-width: 521px)") : css.index("@media (min-width: 521px)") + 1000]
        self.assertIn(".brand-logo-left", desk)
        self.assertIn(".brand-logo-right", desk)
        self.assertIn("display: block", desk)
        # Phone hides left logo + banner
        phone = css[css.index("@media (max-width: 520px)") : css.index("@media (max-width: 520px)") + 2500]
        self.assertIn("brand-logo-left", phone)
        collapsed = re.sub(r"\s+", "", phone.lower())
        self.assertIn("display:none", collapsed)


if __name__ == "__main__":
    unittest.main()
