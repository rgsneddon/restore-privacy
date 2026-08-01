"""Public brand header: phone/Android shows logo only (banner hidden)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestMobileBrandLogoOnly(unittest.TestCase):
    def test_header_markup_still_emits_both_assets(self) -> None:
        """Markup keeps dual logo+banner for desktop; CSS hides twins on phone."""
        from public_chrome import (
            PUBLIC_BRAND_BANNER_PATH,
            PUBLIC_BRAND_LOGO_PATH,
            public_brand_header_html,
        )

        html = public_brand_header_html()
        self.assertIn('class="brand-banner"', html)
        self.assertIn('id="brand-banner"', html)
        self.assertIn("brand-logo-left", html)
        self.assertIn("brand-logo-right", html)
        self.assertIn(PUBLIC_BRAND_BANNER_PATH, html)
        self.assertIn(PUBLIC_BRAND_LOGO_PATH, html)
        mark = html[html.index('id="brand-mark"') : html.index("</header>")]
        self.assertIn("brand-logo", mark)
        self.assertIn("brand-banner", mark)
        # Order: left logo → banner → right logo
        i_l = mark.index("brand-logo-left")
        i_b = mark.index("brand-banner")
        i_r = mark.index("brand-logo-right")
        self.assertLess(i_l, i_b)
        self.assertLess(i_b, i_r)

    def test_phone_css_hides_banner_logo_only(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        self.assertIn("@media (max-width: 520px)", css)

        phone_blocks = re.findall(
            r"@media\s*\(\s*max-width:\s*520px\s*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
            css,
            flags=re.DOTALL,
        )
        self.assertTrue(phone_blocks)
        brand_phone = "\n".join(
            b
            for b in phone_blocks
            if "brand-logo" in b or "brand-banner" in b or "brand-logo-left" in b
        )
        self.assertTrue(brand_phone.strip(), "phone CSS must style brand-logo/banner")

        collapsed = re.sub(r"\s+", "", brand_phone.lower())
        # Banner + left twin hidden on phone / Android
        self.assertIn(".brand-banner", brand_phone)
        self.assertIn("brand-logo-left", brand_phone)
        self.assertIn("display:none", collapsed)
        self.assertRegex(
            brand_phone,
            r"\.brand-banner[^{]*\{[^}]*display:\s*none",
        )
        # Right logo remains visible with non-zero size
        self.assertIn("brand-logo-right", brand_phone)
        self.assertRegex(
            brand_phone,
            r"\.brand-logo-right[^{]*\{[^}]*display:\s*block",
        )
        self.assertIn("min-width: 72px", brand_phone)
        self.assertIn("min-height: 72px", brand_phone)

    def test_desktop_css_keeps_banner_and_logo(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        logo_i = css.index(".brand-logo")
        logo_base = css[logo_i : logo_i + 700]
        self.assertIn("display: block", logo_base)
        ban_i = css.index(".brand-banner")
        ban_base = css[ban_i : ban_i + 500]
        self.assertIn("display: block", ban_base)
        self.assertIn("@media (min-width: 521px)", css)
        desk = css[
            css.index("@media (min-width: 521px)") : css.index("@media (min-width: 521px)")
            + 900
        ]
        self.assertIn(".brand-banner", desk)
        self.assertIn(".brand-logo", desk)
        self.assertIn(".brand-logo-left", desk)
        self.assertIn(".brand-logo-right", desk)
        self.assertIn("display: block", desk)
        # Symmetric gap for equal proximity left/right of banner
        self.assertIn("column-gap", desk)


if __name__ == "__main__":
    unittest.main()
