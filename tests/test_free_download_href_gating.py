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

    def test_render_suite_storefront_five_platform_buttons(self) -> None:
        from downloads import render_suite_storefront_html, suite_pay_href
        from payments import platform_filename

        suite = render_suite_storefront_html()
        self.assertIn("data-pay-packages", suite)
        for plat in PLATFORMS:
            href = suite_pay_href(plat)
            href_html = href.replace("&", "&amp;")
            self.assertIn(href_html, suite)
            self.assertIn(f'data-platform="{plat}"', suite)
            m = re.search(
                rf'href="{re.escape(href_html)}"[^>]*>\s*([^<]+)',
                suite,
            )
            self.assertIsNotNone(m, msg=plat)
            assert m is not None
            self.assertIn(PLATFORM_LABEL[plat], m.group(1), msg=f"{plat}: {m.group(1)!r}")
            fname = platform_filename(plat)
            assert fname is not None
        # Storefront package grid is /pay only (not free suite/download)
        self.assertNotIn("/suite/download?platform=", suite)

    def test_home_and_free_packages_and_public_site(self) -> None:
        from app import render_html
        from downloads import (
            DOWNLOADS_MAP_PATH,
            render_free_download_cta_html,
            render_free_packages_page_html,
            suite_free_direct_download_href,
            suite_pay_href,
        )

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        for plat in PLATFORMS:
            self.assertIn(suite_pay_href(plat).replace("&", "&amp;"), home)

        cta = render_free_download_cta_html()
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', cta)

        for plat in PLATFORMS:
            cta_p = render_free_download_cta_html(default_platform=plat)
            self.assertIn("free_direct=1", cta_p)
            self.assertIn(f"platform={plat}", cta_p)
            self.assertIn(f'data-platform="{plat}"', cta_p)
            self.assertNotIn('href="/pay', cta_p)

        pkgs = render_free_packages_page_html().decode("utf-8")
        for plat in PLATFORMS:
            href_html = suite_pay_href(plat).replace("&", "&amp;")
            self.assertIn(href_html, pkgs)
            self.assertIn(f'data-platform="{plat}"', pkgs)
            m = re.search(
                rf'href="{re.escape(href_html)}"[^>]*>([^<]+)',
                pkgs,
            )
            self.assertIsNotNone(m, msg=plat)
            assert m is not None
            self.assertIn(PLATFORM_LABEL[plat], m.group(1))


if __name__ == "__main__":
    unittest.main()
