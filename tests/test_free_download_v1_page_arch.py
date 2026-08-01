"""Free download v1.0.0 CTA, free-packages page, admin architecture copy."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestFreeDownloadV1CtaAndPage(unittest.TestCase):
    def test_static_freebie_present(self) -> None:
        p = ROOT / "status_page" / "static" / "freebie.jpg"
        self.assertTrue(p.is_file(), p)
        self.assertGreater(p.stat().st_size, 1000)
        self.assertEqual(p.read_bytes()[:2], b"\xff\xd8")

    def test_homepage_full_width_cta_above_stripe_selector(self) -> None:
        from app import render_html
        from downloads import (
            DOWNLOADS_MAP_PATH,
            FREE_DOWNLOAD_CTA_ID,
            FREE_DOWNLOAD_FACE_VERSION,
            FREEBIE_IMG_PATH,
        )

        # No default platform → Downloads Map; OS detect is covered in
        # test_free_download_platform_detect when default_platform is set.
        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = page[page.index('id="page-shell"') :]
        self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', main)
        self.assertIn("freebie", main.lower())
        self.assertIn(FREEBIE_IMG_PATH, main)
        self.assertIn("KEYGEN", main)
        self.assertIn("DOWNLOAD", main)
        self.assertIn(f'data-face-version="{FREE_DOWNLOAD_FACE_VERSION}"', main)
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', main)
        # Full-width CTA styles — full freebie art (contain, not cover crop)
        from downloads import free_download_cta_css

        self.assertIn(".free-download-cta-wrap", page)
        self.assertIn("width: 100%", page)
        cta_css = free_download_cta_css()
        self.assertIn("object-fit: contain", cta_css)
        self.assertNotIn("object-fit: cover", cta_css)
        self.assertIn("a.free-download-cta:active", page)
        self.assertIn("scale(0.985)", page)
        # Order: intro → free CTA → shop (stripe selector in downloads)
        i_intro = main.find("suite-home-intro")
        i_cta = main.index(f'id="{FREE_DOWNLOAD_CTA_ID}"')
        i_shop = main.index('id="home-shop-row"')
        i_dl = main.index('id="downloads"')
        i_buy = main.index("dl-buy-now")
        if i_intro > 0:
            self.assertLess(i_intro, i_cta)
        self.assertLess(i_cta, i_shop)
        self.assertLess(i_cta, i_dl)
        self.assertLess(i_cta, i_buy)

    def test_free_packages_page_orange_links_and_data_path(self) -> None:
        from downloads import (
            FREE_PACKAGES_PATH,
            RELEASE_VERSION,
            list_catalog_platform_packages,
            render_free_packages_page_html,
            suite_free_download_href,
        )

        raw = render_free_packages_page_html()
        html = raw.decode("utf-8")
        self.assertIn('data-free-packages-page="1"', html)
        self.assertIn("data-path", html.lower())
        self.assertIn("data_path_motif", html)
        self.assertIn("#ff7a18", html)  # bold orange
        self.assertIn("Downloads Map", html)
        self.assertIn(RELEASE_VERSION, html)
        pkgs = list_catalog_platform_packages(version=RELEASE_VERSION)
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            plat = p["platform"]
            self.assertIn(suite_free_download_href(plat), html)
            self.assertIn(p["filename"], html)
            self.assertIn(f'data-platform="{plat}"', html)
            self.assertIn(RELEASE_VERSION, p["filename"])

    def test_admin_architecture_free_suite_and_keygen_human_copy(self) -> None:
        from admin_panel import (
            ADMIN_ARCHITECTURE_BLURB,
            ADMIN_ARCHITECTURE_FULL,
            render_admin_home_html,
        )

        full = ADMIN_ARCHITECTURE_FULL
        blurb = ADMIN_ARCHITECTURE_BLURB
        # Free Suite truth
        low = full.lower()
        self.assertIn("free suite installer", low)
        self.assertIn("keygen", low)
        self.assertIn("stripe", low)
        # No lagging “never free” installer claim
        self.assertNotIn("never free permanent GitHub downloads", full)
        self.assertNotIn("Installers are never free", full)
        # Human residual peers
        self.assertIn("Germany", full)
        self.assertIn("Iceland", full)
        page = render_admin_home_html().decode("utf-8")
        self.assertIn("admin-architecture", page)
        self.assertIn("Product architecture (operator)", page)
        # Full body present
        self.assertIn("free suite installer", page.lower())
        self.assertIn(blurb.split(".")[0][:30], page)


if __name__ == "__main__":
    unittest.main()
