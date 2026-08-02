"""Gating: free CTA → free_direct Suite download; other package links → /pay."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

PLATFORMS = ("windows", "android", "macos", "ios", "linux")
PLATFORM_LABEL = {
    "windows": "Windows",
    "android": "Android",
    "macos": "macOS",
    "ios": "iOS",
    "linux": "Linux",
}


class TestFreeDownloadHrefGating(unittest.TestCase):
    def test_suite_free_download_href_helper_all_platforms(self) -> None:
        from downloads import (
            DOWNLOADS_MAP_PATH,
            SUITE_FREE_DOWNLOAD_PATH,
            suite_free_direct_download_href,
            suite_free_download_href,
            suite_pay_href,
        )
        from payments import platform_filename

        self.assertEqual(SUITE_FREE_DOWNLOAD_PATH, "/suite/download")
        self.assertEqual(suite_free_download_href(""), DOWNLOADS_MAP_PATH)
        for plat in PLATFORMS:
            href = suite_free_download_href(plat)
            self.assertEqual(href, f"/suite/download?platform={plat}")
            direct = suite_free_direct_download_href(plat)
            self.assertIn("free_direct=1", direct)
            self.assertIn(f"platform={plat}", direct)
            pay = suite_pay_href(plat)
            self.assertTrue(pay.startswith("/pay?product=suite"))
            self.assertIn(f"platform={plat}", pay)
            fname = platform_filename(plat)
            self.assertIsNotNone(fname)
            assert fname is not None
            self.assertTrue(fname.startswith("restore-privacy-client-"))

    def test_render_suite_storefront_no_platform_grid_or_device_box(self) -> None:
        from downloads import render_suite_storefront_html

        suite = render_suite_storefront_html()
        self.assertIn('id="suite-storefront"', suite)
        self.assertIn("suite-keygen-buy", suite)
        self.assertIn('action="/pay"', suite)
        # Removed: Device for KEYGEN + Get Suite platform button links
        self.assertNotIn("Device for KEYGEN", suite)
        self.assertNotIn('id="suite-keygen-platform"', suite)
        self.assertNotIn('id="suite-free-grid"', suite)
        self.assertNotIn('id="suite-free-primary"', suite)
        self.assertNotIn("Get Suite", suite)
        self.assertNotIn("/suite/download?platform=", suite)

    def test_home_and_free_packages_and_public_site(self) -> None:
        from app import render_html
        from downloads import (
            DOWNLOADS_MAP_PATH,
            render_free_download_cta_html,
            render_free_packages_page_html,
            suite_pay_href,
        )

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        # Suite storefront no longer lists per-platform /pay package buttons
        self.assertNotIn('id="suite-free-grid"', home)
        self.assertNotIn('id="suite-free-primary"', home)
        self.assertNotIn("Device for KEYGEN", home)
        self.assertNotIn('id="suite-keygen-platform"', home)
        self.assertIn("suite-keygen-buy", home)
        self.assertIn('action="/pay"', home)

        cta = render_free_download_cta_html()
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', cta)

        for plat in PLATFORMS:
            cta_p = render_free_download_cta_html(default_platform=plat)
            self.assertIn("free_direct=1", cta_p)
            self.assertIn(f"platform={plat}", cta_p)
            self.assertIn(f'data-platform="{plat}"', cta_p)
            self.assertNotIn('href="/pay', cta_p)

        # Downloads map carries Suite free_direct platform rows
        from downloads import suite_free_direct_download_href

        pkgs = render_free_packages_page_html().decode("utf-8")
        for plat in PLATFORMS:
            href_html = suite_free_direct_download_href(plat).replace("&", "&amp;")
            self.assertIn(href_html, pkgs)
            self.assertIn(f'data-platform="{plat}"', pkgs)
            self.assertIn("free_direct=1", pkgs)
            m = re.search(
                rf'href="{re.escape(href_html)}"[^>]*>([^<]+)',
                pkgs,
            )
            self.assertIsNotNone(m, msg=plat)
            assert m is not None
            self.assertIn(PLATFORM_LABEL[plat], m.group(1))


if __name__ == "__main__":
    unittest.main()
