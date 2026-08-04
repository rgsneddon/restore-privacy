"""Homepage storefront foot download animation under Learn more."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuiteStorefrontDownloadAnim(unittest.TestCase):
    def test_static_media_files_exist_and_are_silent_derivatives(self) -> None:
        static = ROOT / "status_page" / "static"
        mp4 = static / "download_btn_anim.mp4"
        webm = static / "download_btn_anim.webm"
        js = static / "suite_storefront_download_anim.js"
        self.assertTrue(mp4.is_file(), mp4)
        self.assertTrue(webm.is_file(), webm)
        self.assertTrue(js.is_file(), js)
        # Substantially smaller than source (~12MB)
        self.assertLess(mp4.stat().st_size, 2_000_000)
        self.assertGreater(mp4.stat().st_size, 10_000)
        # JS wires free_direct path (shipped client helper, not reimplemented)
        js_src = js.read_text(encoding="utf-8")
        self.assertIn("/suite/download?platform=", js_src)
        self.assertIn("free_direct=1", js_src)
        self.assertIn("suite-storefront-download-anim-link", js_src)

    def test_storefront_renderer_places_anim_under_learn_more(self) -> None:
        from downloads import (
            SUITE_DOWNLOAD_ANIM_ID,
            SUITE_DOWNLOAD_ANIM_LINK_ID,
            SUITE_DOWNLOAD_ANIM_MP4,
            free_download_cta_href,
            render_suite_storefront_html,
            suite_storefront_css,
        )

        html = render_suite_storefront_html(default_platform="android")
        # After Learn more submenu
        sub_i = html.find("suite-product-submenu")
        anim_i = html.find(SUITE_DOWNLOAD_ANIM_ID)
        self.assertGreater(sub_i, 0)
        self.assertGreater(anim_i, sub_i)
        self.assertIn(f'id="{SUITE_DOWNLOAD_ANIM_LINK_ID}"', html)
        self.assertIn(SUITE_DOWNLOAD_ANIM_MP4, html)
        self.assertIn("autoplay", html)
        self.assertIn("muted", html)
        self.assertIn('data-silent="1"', html)
        self.assertIn("loop", html)
        self.assertIn("playsinline", html)
        # Same free download contract as CTA helper
        expected = free_download_cta_href(default_platform="android")
        self.assertIn(expected.replace("&", "&amp;"), html)
        self.assertIn('data-href-kind="suite_free_direct"', html)
        self.assertIn('data-free-direct="1"', html)
        self.assertIn('data-pay="0"', html)
        self.assertIn("/static/suite_storefront_download_anim.js", html)
        # Foot slot constrained — not a fixed native-resolution box
        css = suite_storefront_css()
        self.assertIn("suite-storefront-download-anim", css)
        self.assertIn("object-fit: contain", css)
        self.assertIn("max-height: 14rem", css)
        self.assertIn(
            "video#suite-storefront-download-anim-video",
            css,
        )
        # Video fills foot slot vertically; no 1440px forced on anim rules
        self.assertRegex(
            css,
            r"video#suite-storefront-download-anim-video\s*\{[^}]*height:\s*100%",
        )
        self.assertNotRegex(
            css,
            r"\.suite-storefront-download-anim[^{]*\{[^}]*1440px",
        )

    def test_full_homepage_includes_anim(self) -> None:
        from app import render_html

        page = render_html(
            {"title": "RESTORE PRIVACY"},
            default_platform="macos",
        ).decode("utf-8")
        self.assertIn("suite-storefront-download-anim", page)
        self.assertIn("/static/download_btn_anim.mp4", page)
        # CSS for foot slot present on page (suite_storefront_css is injected)
        self.assertIn("suite-storefront-download-anim", page)
        # Order: Learn more label/nav before anim foot
        self.assertLess(
            page.find("suite-product-submenu"),
            page.find("suite-storefront-download-anim"),
        )
        # Static route registered
        from app import STATIC_ROUTES

        self.assertEqual(
            STATIC_ROUTES.get("/static/download_btn_anim.mp4"),
            "download_btn_anim.mp4",
        )
        self.assertEqual(
            STATIC_ROUTES.get("/static/suite_storefront_download_anim.js"),
            "suite_storefront_download_anim.js",
        )


if __name__ == "__main__":
    unittest.main()
