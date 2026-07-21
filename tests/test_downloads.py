"""Tests for shipped status-page download catalog (RUST-IN-PRIVACY v1.0.0)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    ANDROID_APK_FILENAME,
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

# Exact public release used by the downloads page.
EXPECTED_RELEASE_PAGE = (
    "https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/tag/v1.0.0"
)
EXPECTED_DOWNLOAD_PREFIX = (
    "https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/download/v1.0.0/"
)


class TestDownloadCatalog(unittest.TestCase):
    def test_version_is_rust_1_0_0(self):
        self.assertEqual(RELEASE_VERSION, "1.0.0")
        self.assertEqual(RELEASE_TAG, "v1.0.0")
        self.assertEqual(GITHUB_REPO, "RUST-IN-PRIVACY")
        self.assertEqual(RELEASE_PAGE_URL, EXPECTED_RELEASE_PAGE)
        self.assertEqual(RELEASE_DOWNLOAD_BASE, EXPECTED_DOWNLOAD_PREFIX.rstrip("/"))
        self.assertEqual(RUST_REPO_URL, EXPECTED_RELEASE_PAGE)

    def test_public_assets_include_device_packages(self):
        assets = available_downloads()
        self.assertEqual(len(assets), 5)
        platforms = {a.platform for a in assets}
        self.assertEqual(platforms, {"windows", "linux", "macos", "ios", "android"})
        by_plat = {a.platform: a for a in assets}
        self.assertEqual(by_plat["windows"].filename, WINDOWS_ZIP_FILENAME)
        self.assertTrue(by_plat["windows"].filename.endswith(".zip"))
        self.assertEqual(by_plat["linux"].filename, LINUX_TGZ_FILENAME)
        self.assertEqual(by_plat["macos"].filename, MACOS_ZIP_FILENAME)
        self.assertEqual(by_plat["ios"].filename, IOS_ZIP_FILENAME)
        self.assertEqual(by_plat["android"].filename, ANDROID_APK_FILENAME)
        self.assertTrue(by_plat["android"].filename.endswith(".apk"))
        self.assertEqual(
            by_plat["android"].filename,
            "restore-privacy-rust-1.0.0-android.apk",
        )
        for a in assets:
            self.assertNotIn("apple-prep", a.filename)
            self.assertNotIn("android-prep", a.filename)

    def test_labels_and_html(self):
        html = render_download_section_html()
        self.assertIn("Linux (x64) - Installer (.tar.gz)", html)
        self.assertIn('id="dl-linux"', html)
        self.assertIn("Windows (x64) - Client/Node (.zip)", html)
        self.assertIn('id="dl-macos"', html)
        self.assertIn('id="dl-ios"', html)
        self.assertIn('id="dl-android"', html)
        self.assertIn("macOS - Client (.zip)", html)
        self.assertIn("iOS - Client (.zip)", html)
        self.assertIn("Android - APK installer", html)
        self.assertIn(EXPECTED_RELEASE_PAGE, html)
        self.assertIn("RUST-IN-PRIVACY", html)
        self.assertIn("Windows | Linux | macOS | iOS | Android", html)
        self.assertNotIn("apple-prep", html)

    def test_available_downloads_have_https_github_release_urls(self):
        assets = available_downloads()
        for a in assets:
            self.assertTrue(
                a.url.startswith(EXPECTED_DOWNLOAD_PREFIX),
                f"not explicit v1.0.0 download URL: {a.url}",
            )
            self.assertEqual(a.url, f"{EXPECTED_DOWNLOAD_PREFIX}{a.filename}")
            self.assertNotIn("restore-privacy/releases", a.url)
            self.assertNotIn("href=\"#\"", a.url)
            self.assertNotIn("/download/0.", a.url)
            self.assertNotIn("/tag/", a.url)  # asset links are /download/, not /tag/

    def test_render_download_section_uses_real_urls(self):
        html = render_download_section_html()
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertIn('class="dl"', html)
        self.assertIn("Windows", html)
        self.assertIn("Linux", html)
        self.assertIn(ANDROID_APK_FILENAME, html)
        self.assertIn(EXPECTED_RELEASE_PAGE, html)
        self.assertIn(f'href="{EXPECTED_RELEASE_PAGE}"', html)
        for a in available_downloads():
            self.assertIn(f'href="{a.url}"', html)
            self.assertNotIn('href="#"', html)
            self.assertNotIn("github.com/rgsneddon/restore-privacy/releases", html)

    def test_status_page_html_includes_downloads(self):
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY"}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", page)
        self.assertNotIn("clients-connected", page)
        self.assertNotIn("fetch('/api/status'", page)
        self.assertIn(f"Download client v{RELEASE_VERSION}", page)
        self.assertIn(EXPECTED_DOWNLOAD_PREFIX, page)
        self.assertIn(EXPECTED_RELEASE_PAGE, page)
        self.assertIn(WINDOWS_ZIP_FILENAME, page)
        self.assertIn(LINUX_TGZ_FILENAME, page)
        self.assertIn(MACOS_ZIP_FILENAME, page)
        self.assertIn(IOS_ZIP_FILENAME, page)
        self.assertIn(ANDROID_APK_FILENAME, page)
        self.assertNotIn("apple-prep", page)
        for a in available_downloads():
            self.assertIn(f'href="{a.url}"', page)
            self.assertEqual(
                a.url,
                f"https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/download/v1.0.0/{a.filename}",
            )


if __name__ == "__main__":
    unittest.main()
