"""Public brand header mark: banner only (no dual logo left/right)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestBrandHeaderBannerOnly(unittest.TestCase):
    """Was dual-logo; product now ships banner-only top mark."""

    def test_markup_banner_only_no_flanking_logos(self) -> None:
        from public_chrome import (
            PUBLIC_BRAND_BANNER_PATH,
            PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT,
            PUBLIC_BRAND_LOGO_PATH,
            public_brand_header_html,
        )

        header = public_brand_header_html()
        self.assertIn('data-banner-only="1"', header)
        self.assertNotIn('data-dual-logo="1"', header)
        mark = header[
            header.index('id="brand-mark"') : header.index(
                "</div>", header.index('id="brand-mark"')
            )
        ]
        self.assertIn("brand-banner", mark)
        self.assertNotIn("brand-logo-left", mark)
        self.assertNotIn("brand-logo-right", mark)
        self.assertNotIn('class="brand-logo"', mark)
        self.assertNotIn(PUBLIC_BRAND_LOGO_PATH, mark)
        self.assertIn(PUBLIC_BRAND_BANNER_PATH, mark)
        # Single height attr on the banner img
        h = f'height="{PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT}"'
        self.assertEqual(header.count(h), 1)

    def test_css_hides_logos_shows_banner_all_breakpoints(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        logo_block = css[css.index(".brand-logo") : css.index(".brand-logo") + 400]
        self.assertIn("display: none", logo_block)
        ban_i = css.index(".brand-banner")
        ban_css = css[ban_i : ban_i + 500]
        self.assertIn("display: block", ban_css)
        self.assertIn("var(--rb-brand-header-height)", ban_css)

        self.assertIn("@media (min-width: 521px)", css)
        desk = css[
            css.index("@media (min-width: 521px)") : css.index("@media (min-width: 521px)")
            + 1000
        ]
        self.assertIn(".brand-banner", desk)
        self.assertIn("display: none", desk)  # logos still hidden on desktop

        phone = css[
            css.index("@media (max-width: 520px)") : css.index("@media (max-width: 520px)")
            + 2500
        ]
        collapsed = re.sub(r"\s+", "", phone.lower())
        # Banner visible on phone (not display:none on .brand-banner)
        self.assertIn("img.brand-banner", phone)
        self.assertIn("display:block!important", collapsed)
        # Logos stay hidden
        self.assertIn("display:none!important", collapsed)


if __name__ == "__main__":
    unittest.main()
