"""Gating: every public free-download control targets /suite/download?platform=<known>.

Drives shipped HTML generators + public_site mirror. Platform labels must match
query params; filenames from the catalog helper must contain the platform token.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

PLATFORMS = ("windows", "android", "macos", "ios", "linux")
# Label text substring expected near each platform control (storefront / packages).
PLATFORM_LABEL = {
    "windows": "Windows",
    "android": "Android",
    "macos": "macOS",
    "ios": "iOS",
    "linux": "Linux",
}


def _suite_download_hrefs(html: str) -> list[str]:
    return re.findall(
        r'href="((?:https://restoreprivacy\.online)?/suite/download(?:\?[^"]*)?)"',
        html,
    )


def _normalize(href: str) -> str:
    return href.replace("https://restoreprivacy.online", "")


class TestFreeDownloadHrefGating(unittest.TestCase):
    def test_suite_free_download_href_helper_all_platforms(self) -> None:
        from downloads import SUITE_FREE_DOWNLOAD_PATH, suite_free_download_href
        from payments import platform_filename

        from downloads import DOWNLOADS_MAP_PATH

        self.assertEqual(SUITE_FREE_DOWNLOAD_PATH, "/suite/download")
        # Empty platform → Downloads Map (no dead /suite/download without ?platform=)
        self.assertEqual(suite_free_download_href(""), DOWNLOADS_MAP_PATH)
        for plat in PLATFORMS:
            href = suite_free_download_href(plat)
            self.assertEqual(href, f"/suite/download?platform={plat}")
            fname = platform_filename(plat)
            self.assertIsNotNone(fname)
            assert fname is not None
            # Filename token for this platform (macos/ios use themselves).
            token = plat if plat != "macos" else "macos"
            self.assertIn(token, fname.lower())
            self.assertTrue(fname.startswith("restore-privacy-client-"))

    def test_render_suite_storefront_five_platform_buttons(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            render_suite_storefront_html,
            suite_free_download_href,
        )
        from payments import platform_filename

        suite = render_suite_storefront_html()
        self.assertIn('data-free-download="1"', suite)
        for plat in PLATFORMS:
            href = suite_free_download_href(plat)
            self.assertIn(href, suite)
            self.assertIn(f'data-platform="{plat}"', suite)
            # Label near control matches platform (not a swapped OS).
            m = re.search(
                rf'href="{re.escape(href)}"[^>]*>\s*([^<]+)',
                suite,
            )
            self.assertIsNotNone(m, msg=plat)
            assert m is not None
            label = m.group(1)
            self.assertIn(PLATFORM_LABEL[plat], label, msg=f"{plat}: {label!r}")
            fname = platform_filename(plat)
            assert fname is not None
            self.assertIn(RELEASE_VERSION, fname)

        # No exotic / dead free paths
        for href in _suite_download_hrefs(suite):
            path = _normalize(href)
            m = re.match(r"^/suite/download\?platform=([a-z]+)$", path)
            self.assertIsNotNone(m, msg=path)
            assert m is not None
            self.assertIn(m.group(1), PLATFORMS)

    def test_home_and_free_packages_and_public_site(self) -> None:
        from app import render_html
        from downloads import (
            FREE_PACKAGES_PATH,
            render_free_download_cta_html,
            render_free_packages_page_html,
            suite_free_download_href,
        )

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        for plat in PLATFORMS:
            self.assertIn(suite_free_download_href(plat), home)

        # Default CTA → Downloads Map (no guessed platform without UA).
        from downloads import DOWNLOADS_MAP_PATH

        cta = render_free_download_cta_html()
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', cta)

        # Detected platform CTA → that free installer only.
        for plat in PLATFORMS:
            cta_p = render_free_download_cta_html(default_platform=plat)
            self.assertIn(suite_free_download_href(plat), cta_p)
            self.assertIn(f'data-platform="{plat}"', cta_p)

        pkgs = render_free_packages_page_html().decode("utf-8")
        for plat in PLATFORMS:
            href = suite_free_download_href(plat)
            self.assertIn(href, pkgs)
            self.assertIn(f'data-platform="{plat}"', pkgs)
            m = re.search(
                rf'href="{re.escape(href)}"[^>]*>([^<]+)',
                pkgs,
            )
            self.assertIsNotNone(m, msg=plat)
            assert m is not None
            self.assertIn(PLATFORM_LABEL[plat], m.group(1))

        static = (ROOT / "public_site" / "index.html").read_text(encoding="utf-8")
        for plat in PLATFORMS:
            abs_href = (
                f"https://restoreprivacy.online/suite/download?platform={plat}"
            )
            self.assertIn(abs_href, static)
            # Label on same line / nearby
            self.assertRegex(
                static,
                rf'platform={plat}">Download {re.escape(PLATFORM_LABEL[plat])}',
            )


if __name__ == "__main__":
    unittest.main()
