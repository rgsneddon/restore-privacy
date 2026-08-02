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

    def test_suite_storefront_primary_free_download_for_detected(self) -> None:
        from downloads import (
            render_suite_storefront_html,
            suite_free_download_href,
        )

        html = render_suite_storefront_html(default_platform="macos")
        self.assertIn('id="suite-dl-primary"', html)
        # Shipped storefront primary label (KEYGEN-gated wording)
        self.assertIn("Download for macOS", html)
        self.assertIn("KEYGEN", html)
        self.assertIn(suite_free_download_href("macos"), html)
        self.assertIn('data-detected-platform="macos"', html)
        self.assertIn('id="suite-dl-macos"', html)
        self.assertIn("is-detected", html)
        # All platforms still listed
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(f'data-platform="{plat}"', html)
        # KEYGEN select prefers detected
        self.assertIn('value="macos" selected', html)

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
        # Homepage free CTA (rectangular typewriter) + storefront primary for detected OS
        self.assertIn("FREE DOWNLOAD", page)
        self.assertIn("Download for Windows", page)
        self.assertIn('data-detected-platform="windows"', page)
        self.assertIn('id="suite-dl-primary"', page)
        self.assertIn('id="free-download-v1-cta"', page)
        self.assertIn("/suite/download?platform=windows", page)
        # CTA is text rectangle, not freebie image face
        self.assertIn('data-cta-shape="rectangle"', page)
        cta_i = page.index('id="free-download-v1-cta"')
        cta_snip = page[cta_i : cta_i + 700]
        self.assertNotIn("<img", cta_snip)

    def test_free_download_cta_links_to_detected_os(self) -> None:
        from app import render_html
        from downloads import (
            DOWNLOADS_MAP_PATH,
            FREE_DOWNLOAD_CTA_ID,
            render_free_download_cta_html,
            suite_free_download_href,
        )

        # Direct CTA helper
        cta = render_free_download_cta_html(default_platform="macos")
        self.assertIn(suite_free_download_href("macos"), cta)
        self.assertIn("FREE DOWNLOAD", cta)
        self.assertIn("macOS", cta)  # aria-label names platform
        self.assertIn('data-detected-platform="macos"', cta)
        self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', cta)
        self.assertNotIn(f'href="{DOWNLOADS_MAP_PATH}"', cta)

        # Unknown → Downloads Map
        chooser = render_free_download_cta_html(default_platform="")
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', chooser)
        self.assertNotIn("data-detected-platform", chooser)

        # Homepage wires UA default into the rectangular text CTA
        page = render_html(
            {"title": "RESTORE PRIVACY"}, default_platform="android"
        ).decode("utf-8")
        i_cta = page.index(f'id="{FREE_DOWNLOAD_CTA_ID}"')
        cta_snip = page[i_cta : i_cta + 800]
        self.assertIn(suite_free_download_href("android"), cta_snip)
        self.assertIn("Android", cta_snip)
        self.assertIn('data-detected-platform="android"', cta_snip)
        self.assertIn("FREE DOWNLOAD", cta_snip)
        self.assertIn('data-cta-shape="rectangle"', cta_snip)
        self.assertNotIn("<img", cta_snip)

    def test_free_packages_page_highlights_detected_os(self) -> None:
        from downloads import render_free_packages_page_html, suite_free_download_href

        html = render_free_packages_page_html(default_platform="ios").decode("utf-8")
        self.assertIn('data-detected-platform="ios"', html)
        self.assertIn("Detected your device as <strong>iOS</strong>", html)
        self.assertIn("is-detected", html)
        self.assertIn(suite_free_download_href("ios"), html)
        # Detected Suite iOS installer is marked on the Downloads Map
        self.assertIn('data-platform="ios"', html)
        self.assertIn('data-kind="suite_client"', html)


if __name__ == "__main__":
    unittest.main()
