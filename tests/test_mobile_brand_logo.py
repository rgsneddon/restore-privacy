"""Public brand header: phone/Android shows banner only (no logo fallback)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestMobileBrandBannerOnly(unittest.TestCase):
    def test_header_markup_banner_only(self) -> None:
        """Markup emits banner only at all breakpoints (no dual logos)."""
        from public_chrome import (
            PUBLIC_BRAND_BANNER_PATH,
            PUBLIC_BRAND_LOGO_PATH,
            public_brand_header_html,
        )

        html = public_brand_header_html()
        self.assertIn('class="brand-banner"', html)
        self.assertIn('id="brand-banner"', html)
        self.assertNotIn("brand-logo-left", html)
        self.assertNotIn("brand-logo-right", html)
        self.assertNotIn('class="brand-logo"', html)
        self.assertIn(PUBLIC_BRAND_BANNER_PATH, html)
        self.assertNotIn(PUBLIC_BRAND_LOGO_PATH, html)
        mark = html[html.index('id="brand-mark"') : html.index("</header>")]
        self.assertIn("brand-banner", mark)
        self.assertNotIn("brand-logo", mark)
        self.assertIn('data-banner-only="1"', html)

    def test_phone_css_shows_banner_hides_logos(self) -> None:
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
            if "brand-logo" in b or "brand-banner" in b
        )
        self.assertTrue(brand_phone.strip(), "phone CSS must style brand-banner")

        collapsed = re.sub(r"\s+", "", brand_phone.lower())
        # Banner visible on phone / Android
        self.assertIn(".brand-banner", brand_phone)
        self.assertRegex(
            brand_phone,
            r"\.brand-banner[^{]*\{[^}]*display:\s*block",
        )
        self.assertIn("display:block", collapsed)
        # Logos hidden (not shown as phone fallback)
        self.assertIn(".brand-logo", brand_phone)
        self.assertIn("display:none", collapsed)
        # Must not hide the banner with display:none
        self.assertNotRegex(
            brand_phone,
            r"img\.brand-banner[^{]*\{[^}]*display:\s*none",
        )

    def test_desktop_css_banner_only(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        logo_i = css.index(".brand-logo")
        logo_base = css[logo_i : logo_i + 300]
        self.assertIn("display: none", logo_base)
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
        # Logos remain display:none on desktop
        self.assertIn("display: none", desk)


if __name__ == "__main__":
    unittest.main()
