"""Tests for shipped status-page download catalog (restore-privacy 0.3.0) + paid UI."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    ANDROID_APK_FILENAME,
    BMC_TIP_URL,
    GITHUB_REPO,
    IOS_ZIP_FILENAME,
    LINUX_TGZ_FILENAME,
    MACOS_ZIP_FILENAME,
    RELEASE_DOWNLOAD_BASE,
    RELEASE_PAGE_URL,
    RELEASE_TAG,
    RELEASE_VERSION,
    RUST_REPO_URL,
    WINDOWS_ZIP_FILENAME,
    available_downloads,
    render_download_section_html,
)

EXPECTED_RELEASE_PAGE = (
    "https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.0"
)
EXPECTED_DOWNLOAD_PREFIX = (
    "https://github.com/rgsneddon/restore-privacy/releases/download/0.3.0/"
)
# Public footer points at the paid status host (repo is private).
EXPECTED_PUBLIC_CATALOG_FOOTER = (
    "https://restore-privacy-status.onrender.com/#downloads"
)


class TestDownloadCatalog(unittest.TestCase):
    def test_version_is_0_2_9(self):
        from downloads import (
            catalog_matches_product_pin,
            current_catalog_version,
            is_current_catalog_filename,
        )

        self.assertEqual(RELEASE_VERSION, "0.3.0")
        self.assertEqual(RELEASE_TAG, "0.3.0")
        self.assertEqual(current_catalog_version(), RELEASE_VERSION)
        self.assertTrue(catalog_matches_product_pin())
        self.assertEqual(GITHUB_REPO, "restore-privacy")
        self.assertEqual(RELEASE_PAGE_URL, EXPECTED_RELEASE_PAGE)
        self.assertEqual(RELEASE_DOWNLOAD_BASE, EXPECTED_DOWNLOAD_PREFIX.rstrip("/"))
        self.assertEqual(RUST_REPO_URL, EXPECTED_PUBLIC_CATALOG_FOOTER)
        for a in available_downloads():
            self.assertTrue(is_current_catalog_filename(a.filename))
            self.assertIn(RELEASE_VERSION, a.filename)
        self.assertFalse(
            is_current_catalog_filename(
                "restore-privacy-client-0.2.9-windows-x64-setup.exe"
            )
        )

    def test_public_assets_include_device_packages(self):
        assets = available_downloads()
        self.assertEqual(len(assets), 5)
        platforms = {a.platform for a in assets}
        self.assertEqual(platforms, {"windows", "linux", "macos", "ios", "android"})
        by_plat = {a.platform: a for a in assets}
        self.assertEqual(by_plat["windows"].filename, WINDOWS_ZIP_FILENAME)
        self.assertEqual(by_plat["linux"].filename, LINUX_TGZ_FILENAME)
        self.assertEqual(by_plat["macos"].filename, MACOS_ZIP_FILENAME)
        self.assertEqual(by_plat["ios"].filename, IOS_ZIP_FILENAME)
        self.assertEqual(by_plat["android"].filename, ANDROID_APK_FILENAME)
        for a in assets:
            self.assertEqual(a.url, f"{EXPECTED_DOWNLOAD_PREFIX}{a.filename}")
            self.assertIn("donate.stripe.com", a.pay_path)
            self.assertIn(f"client_reference_id={a.platform}", a.pay_path)

    def test_labels_and_html_paid(self):
        html = render_download_section_html()
        self.assertIn("Linux (x64) - Installer (.tar.gz)", html)
        self.assertIn('id="dl-linux"', html)
        self.assertIn("Windows (x64) - Installer (.exe)", html)
        self.assertIn("Developer ID + notarized", html)
        self.assertIn("Team-signed sideload", html)
        self.assertIn('id="dl-android"', html)
        self.assertIn("£2.45", html)
        self.assertIn(BMC_TIP_URL, html)
        self.assertIn(EXPECTED_PUBLIC_CATALOG_FOOTER, html)
        self.assertIn("Pay £2.45", html)
        # Free permanent GitHub installer hrefs must not appear in public HTML.
        self.assertNotIn("releases/download/0.3.0/", html)
        for a in available_downloads():
            self.assertIn(f'href="{a.pay_path}"', html)
            self.assertIn(f"client_reference_id={a.platform}", html)
            self.assertNotIn(f'href="{a.url}"', html)

    def test_available_downloads_have_https_github_release_urls(self):
        for a in available_downloads():
            self.assertTrue(a.url.startswith(EXPECTED_DOWNLOAD_PREFIX))
            self.assertEqual(a.url, f"{EXPECTED_DOWNLOAD_PREFIX}{a.filename}")

    def test_render_download_section_uses_paid_paths(self):
        html = render_download_section_html()
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertIn('class="dl"', html)
        self.assertNotIn('href="#"', html)
        self.assertIn("data-price-pence=\"245\"", html)

    def test_download_section_omits_long_pay_flow_copy(self):
        """Public downloads: no long session-id success-page explainer block."""
        html = render_download_section_html()
        self.assertNotIn("Each button opens the payment page", html)
        self.assertNotIn("Direct package files are not linked until paid", html)
        self.assertNotIn('id="dl-pay-flow"', html)
        self.assertNotIn('id="dl-claim-hint"', html)
        self.assertNotIn("/download/success?session_id=", html)
        # Pay buttons still present and usable
        self.assertIn("Pay £2.45", html)
        self.assertIn('id="dl-windows"', html)
        self.assertIn("client_reference_id=windows", html)
        self.assertIn("donate.stripe.com", html)

    def test_status_page_html_includes_paid_downloads(self):
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", page)
        self.assertNotIn("clients-connected", page)
        self.assertIn(f"Download client v{RELEASE_VERSION}", page)
        self.assertIn("donate.stripe.com", page)
        self.assertIn("client_reference_id=windows", page)
        self.assertIn("£2.45", page)
        self.assertIn(WINDOWS_ZIP_FILENAME, page)  # data-filename
        self.assertIn(ANDROID_APK_FILENAME, page)
        self.assertIn(BMC_TIP_URL, page)


if __name__ == "__main__":
    unittest.main()
