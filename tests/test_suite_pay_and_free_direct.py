"""Suite package links → /pay; free CTA → direct Suite download (no /pay)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuitePayHrefBuilders(unittest.TestCase):
    def test_pay_and_free_direct_hrefs(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            available_downloads,
            free_download_cta_href,
            list_downloads_map_rows,
            suite_free_direct_download_href,
            suite_pay_href,
        )

        for plat in ("windows", "macos", "linux", "android", "ios"):
            pay = suite_pay_href(plat)
            self.assertTrue(pay.startswith("/pay?"), pay)
            self.assertIn("product=suite", pay)
            self.assertIn(f"platform={plat}", pay)
            direct = suite_free_direct_download_href(plat)
            self.assertIn("/suite/download?", direct)
            self.assertIn(f"platform={plat}", direct)
            self.assertIn("free_direct=1", direct)
            self.assertNotIn("/pay", direct)
            self.assertEqual(free_download_cta_href(default_platform=plat), direct)

        self.assertEqual(free_download_cta_href(default_platform=""), "/downloads-map")
        self.assertEqual(free_download_cta_href(default_platform="unknown"), "/downloads-map")

        rows = list_downloads_map_rows()
        self.assertEqual(len(rows), len(available_downloads()))
        for r in rows:
            self.assertEqual(r["kind"], "suite_client")
            self.assertEqual(r["version"], RELEASE_VERSION)
            self.assertEqual(r["product"], "Restore Privacy Suite")
            self.assertTrue(r["href"].startswith("/pay?product=suite"))
            self.assertIn("platform=", r["href"])
        kinds = {r["kind"] for r in rows}
        self.assertEqual(kinds, {"suite_client"})
        # No non-Suite products
        blob = " ".join(r["product"] + r["kind"] + r["filename"] for r in rows).lower()
        for banned in ("pens", "tables", "slides", "rpos", "browser", "extension", "beam"):
            self.assertNotIn(banned, blob)


class TestHomeAndMapRender(unittest.TestCase):
    def test_home_free_cta_direct_others_pay(self) -> None:
        from app import render_html
        from downloads import (
            FREE_DOWNLOAD_CTA_ID,
            RELEASE_VERSION,
            free_download_cta_href,
            render_downloads_map_page_html,
            render_free_download_cta_html,
            render_suite_storefront_html,
            suite_pay_href,
        )

        for _ in range(2):
            page = render_html(
                {"title": "RESTORE PRIVACY"}, default_platform="macos"
            ).decode("utf-8")
            cta = render_free_download_cta_html(default_platform="macos")
            # href is HTML-escaped (&amp;) in attributes
            self.assertIn("platform=macos", cta)
            self.assertIn("free_direct=1", cta)
            self.assertIn("/suite/download?", cta)
            self.assertNotIn('href="/pay', cta)
            self.assertIn("data-pay=\"0\"", cta)
            self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', page)
            self.assertIn("free_direct=1", page)

            suite = render_suite_storefront_html(default_platform="macos")
            # HTML attributes escape & → &amp;
            self.assertIn(suite_pay_href("macos").replace("&", "&amp;"), suite)
            self.assertIn(suite_pay_href("windows").replace("&", "&amp;"), suite)
            # Platform grid must not advertise ungated free suite/download
            self.assertNotIn("/suite/download?platform=", suite)
            self.assertIn("/pay?product=suite", suite)
            self.assertIn("platform=linux", suite)

            map_html = render_downloads_map_page_html().decode("utf-8")
            self.assertIn("Restore Privacy Suite", map_html)
            self.assertIn(f"v{RELEASE_VERSION}", map_html)
            self.assertIn("/pay?product=suite", map_html)
            for plat in ("windows", "android", "macos", "ios", "linux"):
                self.assertIn(suite_pay_href(plat).replace("&", "&amp;"), map_html)
            # Map is Suite-only — no companion product sections
            self.assertNotIn("data-kind=\"browser\"", map_html)
            self.assertNotIn("data-kind=\"pens\"", map_html)
            self.assertNotIn("rx-browser", map_html.lower().replace(" ", ""))

            # Order free CTA after intro, before shop
            i_intro = page.index('id="suite-home-intro"')
            i_cta = page.index(f'id="{FREE_DOWNLOAD_CTA_ID}"')
            i_shop = page.index('id="home-shop-row"')
            self.assertLess(i_intro, i_cta)
            self.assertLess(i_cta, i_shop)

    def test_free_cta_two_platforms_never_pay(self) -> None:
        from downloads import free_download_cta_href, suite_free_direct_download_href

        for plat in ("windows", "linux"):
            href = free_download_cta_href(default_platform=plat)
            self.assertEqual(href, suite_free_direct_download_href(plat))
            self.assertIn(f"platform={plat}", href)
            self.assertIn("free_direct=1", href)
            self.assertFalse(href.startswith("/pay"))


if __name__ == "__main__":
    unittest.main()
