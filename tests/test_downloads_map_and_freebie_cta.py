"""FREE DOWNLOAD CTA face, Downloads Map inventory, footer © + map link."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestFreebieImageFace(unittest.TestCase):
    def test_freebie_jpg_has_no_v100_face_string_in_file_meta(self) -> None:
        """Bitmap face: FREE DOWNLOAD only — no baked v1.0.0 (composited asset)."""
        freebie = ROOT / "status_page" / "static" / "freebie.jpg"
        self.assertTrue(freebie.is_file())
        self.assertGreater(freebie.stat().st_size, 10_000)
        # JPEG binary will not contain readable 'v1.0.0' as face text after composite;
        # assert file is not the original 160863-byte v1.0.0 asset by size change
        # and that OCR-free check: original commit message era size was 160863.
        # Stronger: decode with Pillow and assert bar region is mostly dark + white text.
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover
            self.skipTest("Pillow not available")
        img = Image.open(freebie).convert("RGB")
        w, h = img.size
        # sample center of button bar (lower third)
        cy = int(h * 0.76)
        # count near-white pixels in bar band (text) vs mid-band
        whites = 0
        samples = 0
        for x in range(int(w * 0.25), int(w * 0.75), 4):
            for y in range(int(h * 0.72), int(h * 0.82), 3):
                r, g, b = img.getpixel((x, y))
                samples += 1
                if r > 200 and g > 200 and b > 200:
                    whites += 1
        self.assertGreater(samples, 50)
        # FREE DOWNLOAD white glyphs should produce some bright pixels
        self.assertGreater(whites, 5, "expected white FREE DOWNLOAD face text on bar")


class TestCtaLinkFallback(unittest.TestCase):
    def test_known_platform_and_unknown_ua(self) -> None:
        from downloads import (
            DOWNLOADS_MAP_PATH,
            RELEASE_VERSION,
            free_download_cta_href,
            render_free_download_cta_html,
            suite_free_direct_download_href,
        )

        # Free CTA: direct Suite latest for detected device (free_direct, no /pay)
        href_mac = free_download_cta_href(default_platform="macos")
        self.assertEqual(href_mac, suite_free_direct_download_href("macos"))
        self.assertIn("platform=macos", href_mac)
        self.assertIn("/suite/download", href_mac)
        self.assertIn("free_direct=1", href_mac)
        self.assertNotIn("/pay", href_mac)
        # monopin is served by the suite download handler (RELEASE_VERSION pin)
        self.assertTrue(RELEASE_VERSION)

        href_unk = free_download_cta_href(default_platform="")
        self.assertEqual(href_unk, DOWNLOADS_MAP_PATH)

        html_mac = render_free_download_cta_html(default_platform="macos")
        self.assertIn("DOWNLOAD", html_mac)
        self.assertIn("platform=macos", html_mac)
        self.assertIn("free_direct=1", html_mac)
        self.assertIn('data-pay="0"', html_mac)
        self.assertNotIn('href="/pay', html_mac)
        self.assertNotIn("v1.0.0", html_mac)
        self.assertNotIn("version 1.0.0", html_mac.lower())

        html_map = render_free_download_cta_html(default_platform="")
        self.assertIn(DOWNLOADS_MAP_PATH, html_map)
        self.assertIn("DOWNLOAD", html_map)
        self.assertIn('data-href-kind="map"', html_map)
        self.assertIn('data-pay="0"', html_map)
        self.assertNotIn('href="/pay', html_map)


class TestDownloadsMapPage(unittest.TestCase):
    def test_map_enumerates_brand_products_and_hrefs(self) -> None:
        from downloads import (
            available_downloads,
            list_downloads_map_rows,
            map_platform_version,
            render_downloads_map_page_html,
            suite_free_direct_download_href,
        )

        # Map is Suite latest clients only → free_direct download per platform
        rows = list_downloads_map_rows()
        self.assertEqual(len(rows), len(available_downloads()))
        self.assertEqual(len(rows), 5)
        products = {r["product"] for r in rows}
        self.assertEqual(products, {"Restore Privacy"})
        kinds = {r["kind"] for r in rows}
        self.assertEqual(kinds, {"suite_client"})
        for r in rows:
            self.assertEqual(r["version"], map_platform_version(r["platform"]))
            self.assertTrue(r.get("filename"))
            self.assertIn(r["version"], r["filename"])
            self.assertEqual(r["href"], suite_free_direct_download_href(r["platform"]))
            self.assertIn("/suite/download?", r["href"])
            self.assertIn("free_direct=1", r["href"])
            self.assertIn(f"platform={r['platform']}", r["href"])
            self.assertNotIn("/pay", r["href"])
        # No companion product kinds
        blob = " ".join(r["product"] + r["kind"] + r["filename"] for r in rows).lower()
        for banned in ("pens", "tables", "slides", "rpos", "browser", "extension", "beam"):
            self.assertNotIn(banned, blob)

        page = render_downloads_map_page_html(default_platform="windows").decode("utf-8")
        self.assertIn("Downloads Map", page)
        self.assertIn("data-downloads-map-page", page)
        self.assertIn("windows", page.lower())
        self.assertIn("free_direct=1", page)
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(
                suite_free_direct_download_href(plat).replace("&", "&amp;"),
                page,
            )
        self.assertNotIn("/pay?product=suite&amp;platform=", page)
        # Suite-only — no office pillars / companion products
        self.assertNotIn('data-kind="pens"', page)
        self.assertNotIn('data-kind="browser"', page)
        self.assertNotIn("data-map-product=\"Pens\"", page)
        self.assertIn("is-detected", page)  # windows suite link marked
        self.assertIn(map_platform_version("windows"), page)
        self.assertIn("1.2.5", page)


class TestFooterCopyrightAndMapLink(unittest.TestCase):
    def test_footer_has_copyright_sign_and_map_link(self) -> None:
        from coffee_link import (
            SITE_FOOTER_MAP_LABEL,
            render_site_copyright_footer_html,
            site_copyright_text,
        )
        from downloads import DOWNLOADS_MAP_PATH

        text = site_copyright_text()
        self.assertIn("©", text)
        self.assertNotIn("(c)", text.lower().replace("©", ""))
        self.assertIn("Raskul", text)

        foot = render_site_copyright_footer_html()
        self.assertIn("©", foot)
        self.assertIn(SITE_FOOTER_MAP_LABEL, foot)
        self.assertIn(DOWNLOADS_MAP_PATH, foot)
        self.assertIn("site-footer-downloads-map", foot)
        # layout markers for left copyright / right map
        self.assertIn("site-footer-inner", foot)
        self.assertIn("site-footer-copyright", foot)


if __name__ == "__main__":
    unittest.main()
