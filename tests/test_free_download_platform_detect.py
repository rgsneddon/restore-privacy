"""Free Suite download: detect viewer OS brand from User-Agent."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestDetectPlatformFromUserAgent(unittest.TestCase):
    def test_common_user_agents(self) -> None:
        from downloads import detect_platform_from_user_agent

        cases = [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
                "windows",
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
                "macos",
            ),
            (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                "ios",
            ),
            (
                "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                "ios",
            ),
            (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile",
                "android",
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0",
                "linux",
            ),
            (
                "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36",
                "linux",
            ),
            ("", ""),
            ("TotallyUnknownBrowser/1.0", ""),
        ]
        for ua, want in cases:
            self.assertEqual(
                detect_platform_from_user_agent(ua),
                want,
                msg=f"ua={ua!r}",
            )

    def test_suite_storefront_keygen_without_device_grid(self) -> None:
        from downloads import render_suite_storefront_html, suite_free_download_href

        html = render_suite_storefront_html(default_platform="macos")
        # Detected platform still marked on section; no package grid / device box
        self.assertIn('data-detected-platform="macos"', html)
        self.assertIn("KEYGEN", html)
        self.assertIn('action="/pay"', html)
        self.assertIn("suite-keygen-buy", html)
        self.assertNotIn('id="suite-dl-primary"', html)
        self.assertNotIn('id="suite-free-grid"', html)
        self.assertNotIn("Device for KEYGEN", html)
        self.assertNotIn('id="suite-keygen-platform"', html)
        self.assertNotIn(suite_free_download_href("macos"), html)
        self.assertNotIn("Get Suite", html)

    def test_homepage_uses_user_agent_when_no_query_platform(self) -> None:
        from app import render_html
        from downloads import detect_platform_from_user_agent

        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.assertEqual(detect_platform_from_user_agent(ua), "windows")
        # Mirror what the homepage does when q_plat empty
        plat = detect_platform_from_user_agent(ua)
        page = render_html({"title": "RESTORE PRIVACY"}, default_platform=plat).decode(
            "utf-8"
        )
        # Homepage free CTA = direct Suite free_direct; storefront KEYGEN cart only
        self.assertIn("FREE DOWNLOAD", page)
        self.assertIn("free_direct=1", page)
        self.assertIn("platform=windows", page)
        self.assertIn("/suite/download?platform=windows", page)
        self.assertIn('data-detected-platform="windows"', page)
        self.assertNotIn('id="suite-dl-primary"', page)
        self.assertNotIn('id="suite-free-grid"', page)
        self.assertNotIn("Device for KEYGEN", page)
        self.assertNotIn('id="suite-keygen-platform"', page)
        self.assertIn("suite-keygen-buy", page)
        self.assertIn('id="free-download-v1-cta"', page)
        self.assertIn('data-cta-shape="rectangle"', page)
        cta_i = page.index('id="free-download-v1-cta"')
        cta_snip = page[cta_i : cta_i + 900]
        self.assertNotIn("<img", cta_snip)
        self.assertIn("free_direct=1", cta_snip)
        self.assertNotIn("/pay", cta_snip)

    def test_free_download_cta_links_to_detected_os(self) -> None:
        from app import render_html
        from downloads import (
            DOWNLOADS_MAP_PATH,
            FREE_DOWNLOAD_CTA_ID,
            render_free_download_cta_html,
            suite_free_download_href,
        )

        from downloads import suite_free_direct_download_href

        # Direct CTA helper — free_direct Suite path (not /pay)
        cta = render_free_download_cta_html(default_platform="macos")
        self.assertIn("platform=macos", cta)
        self.assertIn("free_direct=1", cta)
        self.assertIn("/suite/download?", cta)
        self.assertIn("FREE DOWNLOAD", cta)
        self.assertIn("macOS", cta)
        self.assertNotIn('href="/pay', cta)
        self.assertIn('data-detected-platform="macos"', cta)
        self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', cta)
        self.assertNotIn(f'href="{DOWNLOADS_MAP_PATH}"', cta)

        # Unknown → Downloads Map (no platform picker on free button)
        chooser = render_free_download_cta_html(default_platform="")
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', chooser)
        self.assertNotIn("data-detected-platform", chooser)

        # Homepage wires UA default into free_direct CTA
        page = render_html(
            {"title": "RESTORE PRIVACY"}, default_platform="android"
        ).decode("utf-8")
        i_cta = page.index(f'id="{FREE_DOWNLOAD_CTA_ID}"')
        cta_snip = page[i_cta : i_cta + 900]
        self.assertIn("platform=android", cta_snip)
        self.assertIn("free_direct=1", cta_snip)
        self.assertIn("Android", cta_snip)
        self.assertIn('data-detected-platform="android"', cta_snip)
        self.assertIn("FREE DOWNLOAD", cta_snip)
        self.assertIn('data-cta-shape="rectangle"', cta_snip)
        self.assertNotIn("<img", cta_snip)
        self.assertNotIn('href="/pay', cta_snip)

    def test_free_packages_page_highlights_detected_os(self) -> None:
        from downloads import (
            render_free_packages_page_html,
            suite_free_direct_download_href,
            suite_pay_href,
        )

        html = render_free_packages_page_html(default_platform="ios").decode("utf-8")
        self.assertIn('data-detected-platform="ios"', html)
        self.assertIn("Detected your device as <strong>iOS</strong>", html)
        self.assertIn("is-detected", html)
        # Map Suite rows free_direct download (same as FREE DOWNLOAD), not /pay
        direct = suite_free_direct_download_href("ios").replace("&", "&amp;")
        self.assertIn(direct, html)
        self.assertIn("free_direct=1", html)
        self.assertNotIn(suite_pay_href("ios").replace("&", "&amp;"), html)
        self.assertIn('data-platform="ios"', html)
        self.assertIn('data-kind="suite_client"', html)


if __name__ == "__main__":
    unittest.main()
