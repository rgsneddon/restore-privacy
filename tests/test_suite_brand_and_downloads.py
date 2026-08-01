"""Public product brand is Suite; all catalog download links pin RELEASE_VERSION."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

from downloads import RELEASE_VERSION as SUITE_PIN  # noqa: E402


class TestSuiteBrandSurfaces(unittest.TestCase):
    def test_homepage_and_public_docs_product_name_is_suite(self) -> None:
        from app import render_html
        from downloads import render_download_section_html, render_suite_storefront_html
        from public_chrome import PUBLIC_BRAND_TITLE, public_display_title
        from public_docs import load_public_document_bytes

        self.assertEqual(PUBLIC_BRAND_TITLE, "RESTORE PRIVACY SUITE")
        self.assertEqual(
            public_display_title("RESTORE PRIVACY VPN"), "RESTORE PRIVACY SUITE"
        )

        home = render_html({"title": "RESTORE PRIVACY VPN"}).decode("utf-8")
        # Product title in tab
        self.assertIn("<title>RESTORE PRIVACY SUITE</title>", home)
        self.assertNotIn("<title>RESTORE PRIVACY VPN</title>", home)
        # Body product identity
        self.assertIn("Restore Privacy Suite", home)
        self.assertNotIn("Restore Privacy VPN", home)
        self.assertNotIn("RESTORE PRIVACY VPN", home)

        suite = render_suite_storefront_html()
        self.assertIn("Restore Privacy Suite", suite)
        self.assertNotIn("Restore Privacy VPN", suite)

        dl = render_download_section_html()
        self.assertIn("Download Suite client", dl)
        self.assertIn(f"v{SUITE_PIN}", dl)
        self.assertNotIn("Restore Privacy VPN", dl)

        # Current-facing public pack docs
        for name in ("README.md", "PRIVACY_POLICY.md", "LICENSE"):
            raw = load_public_document_bytes(name, min_size=100)
            self.assertIsNotNone(raw, name)
            assert raw is not None
            text = raw.decode("utf-8")
            self.assertNotIn("Restore Privacy VPN", text, msg=name)
            self.assertNotIn("RESTORE PRIVACY VPN", text, msg=name)
            if name != "LICENSE":
                self.assertIn("Restore Privacy Suite", text, msg=name)
            else:
                self.assertIn("Restore Privacy Suite", text)

    def test_connect_and_tester_copy_use_suite(self) -> None:
        from connect_web import ACTION_LINE, render_connect_via_web_html
        from tester_page import ALREADY_USED_MESSAGE

        self.assertIn("Restore Privacy Suite", ACTION_LINE)
        self.assertNotIn("Restore Privacy VPN", ACTION_LINE)
        self.assertIn(SUITE_PIN, ACTION_LINE)

        frag = render_connect_via_web_html()
        self.assertIn("Restore Privacy Suite", frag)
        self.assertNotIn("Restore Privacy VPN", frag)
        self.assertIn(f'data-catalog-version="{SUITE_PIN}"', frag)

        self.assertIn("Restore Privacy Suite", ALREADY_USED_MESSAGE)
        self.assertNotIn("Restore Privacy VPN", ALREADY_USED_MESSAGE)

    def test_browser_extension_product_chrome_is_suite(self) -> None:
        ext = ROOT / "browser_extension"
        manifest = (ext / "manifest.json").read_text(encoding="utf-8")
        popup = (ext / "popup.html").read_text(encoding="utf-8")
        core = (ext / "lib" / "vpn_core.js").read_text(encoding="utf-8")
        for blob, label in (
            (manifest, "manifest"),
            (popup, "popup"),
            (core, "vpn_core"),
        ):
            self.assertNotIn("Restore Privacy VPN", blob, msg=label)
            self.assertNotIn("RESTORE PRIVACY VPN", blob, msg=label)
        self.assertIn("Restore Privacy Suite", manifest)
        self.assertIn("RESTORE PRIVACY SUITE", popup)
        self.assertIn("RESTORE PRIVACY SUITE", core)
        self.assertIn('"name": "Restore Privacy Suite"', manifest)


class TestSuiteDownloadsMonopinCurrent(unittest.TestCase):
    def test_catalog_and_free_package_links_match_release(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            available_downloads,
            list_catalog_platform_packages,
            render_free_packages_page_html,
            render_suite_storefront_html,
            suite_free_download_href,
        )

        self.assertEqual(RELEASE_VERSION, SUITE_PIN)
        assets = available_downloads()
        self.assertGreaterEqual(len(assets), 5)
        for a in assets:
            self.assertIn(SUITE_PIN, a.filename)
            self.assertTrue(
                a.filename.startswith(f"restore-privacy-client-{SUITE_PIN}-"),
                msg=a.filename,
            )
            # No older catalog pins in live filenames
            self.assertNotRegex(a.filename, r"0\.\d+\.\d+")

        pkgs = list_catalog_platform_packages(version=SUITE_PIN)
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], SUITE_PIN)
            self.assertIn(SUITE_PIN, p["filename"])
            href = suite_free_download_href(p["platform"])
            self.assertIn(f"platform={p['platform']}", href)

        suite = render_suite_storefront_html()
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(suite_free_download_href(plat), suite)
        # Free package filenames on free-packages page
        free = render_free_packages_page_html(version=SUITE_PIN).decode("utf-8")
        for p in pkgs:
            self.assertIn(p["filename"], free)
            self.assertIn(suite_free_download_href(p["platform"]), free)
        self.assertNotIn("0.5.", free)
        self.assertNotIn("0.4.", free)

    def test_homepage_download_section_pins_release(self) -> None:
        from app import render_html
        from downloads import RELEASE_VERSION

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertEqual(RELEASE_VERSION, SUITE_PIN)
        self.assertIn(f"Download Suite client v{SUITE_PIN}", html)
        self.assertIn(f'data-catalog-version="{SUITE_PIN}"', html)
        # Free Suite download routes present
        self.assertIn("/suite/download?platform=", html)
        # No legacy 0.x installer filenames on the live page
        self.assertIsNone(re.search(r"restore-privacy-client-0\.\d+\.\d+-", html))


if __name__ == "__main__":
    unittest.main()
