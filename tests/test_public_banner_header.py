"""Public brand header: full-width banner.jpg + logo, sharp sizing (no VPN H1)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestPublicBannerHeader(unittest.TestCase):
    def test_banner_static_asset_present(self) -> None:
        p = ROOT / "status_page" / "static" / "banner.jpg"
        self.assertTrue(p.is_file(), f"missing {p}")
        self.assertGreater(p.stat().st_size, 1000)
        # JPEG magic
        self.assertEqual(p.read_bytes()[:2], b"\xff\xd8")

    def test_header_logo_and_banner_same_height_no_vpn_h1(self) -> None:
        from public_chrome import (
            PUBLIC_BRAND_BANNER_PATH,
            PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT,
            PUBLIC_BRAND_LOGO_PATH,
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_site_css,
        )

        html = public_brand_header_html()
        self.assertIn('class="brand-logo"', html)
        self.assertIn('class="brand-banner"', html)
        self.assertIn(PUBLIC_BRAND_BANNER_PATH, html)
        self.assertIn(PUBLIC_BRAND_LOGO_PATH, html)
        # No visible VPN heading text
        self.assertNotIn(f"<h1>{PUBLIC_BRAND_TITLE}</h1>", html)
        self.assertNotRegex(html, r"<h1>\s*RESTORE PRIVACY VPN\s*</h1>")
        # Equal height attributes
        heights = re.findall(r'height="(\d+)"', html)
        self.assertGreaterEqual(len(heights), 2)
        self.assertEqual(heights[0], heights[1])
        self.assertEqual(int(heights[0]), PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT)
        # Sharp display height is not a tiny sub-72 strip
        self.assertGreaterEqual(PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT, 100)

        css = public_site_css()
        self.assertIn("--rb-brand-header-height", css)
        # Both logo and banner use the shared CSS variable for height
        self.assertIn(
            "height: var(--rb-brand-header-height)",
            css,
        )
        # Count: logo block + banner block
        self.assertGreaterEqual(
            css.count("height: var(--rb-brand-header-height)"),
            2,
        )

    def test_brand_mark_full_content_width_and_sharp(self) -> None:
        """Logo+banner span full brand-mark / content width (not a ~36rem strip)."""
        from public_chrome import (
            PUBLIC_BRAND_BANNER_PATH,
            PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT,
            PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS,
            PUBLIC_BRAND_HEADER_HEIGHT_MIN_CSS,
            PUBLIC_BRAND_LOGO_PATH,
            public_brand_header_html,
            public_site_css,
        )

        html = public_brand_header_html()
        self.assertIn('data-brand-mark="1"', html)
        self.assertIn('id="brand-banner"', html)
        self.assertIn(PUBLIC_BRAND_BANNER_PATH, html)
        self.assertIn(PUBLIC_BRAND_LOGO_PATH, html)
        self.assertIn("banner.jpg", html)
        self.assertIn("logo_transparent", html)

        css = public_site_css()
        # Extract brand-mark / logo / banner rule blocks from shipped CSS
        mark_i = css.index(".brand-mark")
        mark_css = css[mark_i : mark_i + 500]
        self.assertIn("width: 100%", mark_css)
        self.assertIn("max-width: 100%", mark_css)

        logo_i = css.index(".brand-logo")
        logo_css = css[logo_i : logo_i + 700]
        self.assertIn("object-fit: contain", logo_css)
        self.assertIn("var(--rb-brand-header-height)", logo_css)
        self.assertIn("image-rendering", logo_css)

        ban_i = css.index(".brand-banner")
        ban_css = css[ban_i : ban_i + 900]
        self.assertIn("width: 100%", ban_css)
        self.assertIn("max-width: 100%", ban_css)
        self.assertIn("object-fit: contain", ban_css)
        self.assertIn("var(--rb-brand-header-height)", ban_css)
        self.assertIn("image-rendering", ban_css)
        # Must not reintroduce the narrow banner strip cap
        self.assertNotIn("36rem", ban_css)
        self.assertNotIn("max-width: min(100%, 36rem)", ban_css)
        self.assertNotIn("max-width: 36rem", ban_css)
        # Phone: banner hidden, logo only (see test_mobile_brand_logo)
        self.assertIn("@media (max-width: 520px)", css)
        phone = css[css.index("@media (max-width: 520px)") :]
        self.assertIn(".brand-banner", phone)
        self.assertIn("display: none", phone)

        # Height clamp allows a taller, sharper full-width banner
        self.assertIn(f"{PUBLIC_BRAND_HEADER_HEIGHT_MIN_CSS}px", css)
        self.assertIn(f"{PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS}px", css)
        self.assertGreaterEqual(PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS, 160)
        self.assertGreaterEqual(PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT, 100)
        self.assertLessEqual(
            PUBLIC_BRAND_HEADER_HEIGHT_MIN_CSS, PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT
        )
        self.assertLessEqual(
            PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT, PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS
        )
        # Shared height attr still equal on both imgs
        self.assertEqual(
            html.count(f'height="{PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT}"'),
            2,
        )

    def test_app_static_routes_map_banner(self) -> None:
        from app import STATIC_ROUTES

        self.assertEqual(STATIC_ROUTES.get("/banner.jpg"), "banner.jpg")
        self.assertEqual(STATIC_ROUTES.get("/static/banner.jpg"), "banner.jpg")


if __name__ == "__main__":
    unittest.main()
