"""Tests for shipped status-page download catalog (current RELEASE_VERSION)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    ANDROID_APK_FILENAME,
    IOS_ZIP_FILENAME,
    MACOS_ZIP_FILENAME,
    RELEASE_TAG,
    RELEASE_VERSION,
    WINDOWS_EXE_FILENAME,
    available_downloads,
    render_download_section_html,
)


class TestDownloadCatalog(unittest.TestCase):
    def test_version_matches_client_version_file(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(RELEASE_VERSION, ver)
        self.assertEqual(RELEASE_TAG, ver)
        self.assertEqual(RELEASE_VERSION, "0.2.1")

    def test_public_assets_include_all_platforms(self):
        assets = available_downloads()
        self.assertEqual(len(assets), 5)
        platforms = {a.platform for a in assets}
        self.assertEqual(
            platforms, {"windows", "android", "macos", "ios", "linux"}
        )
        by_plat = {a.platform: a for a in assets}
        self.assertTrue(by_plat["windows"].filename.endswith(".exe"))
        self.assertEqual(by_plat["windows"].filename, WINDOWS_EXE_FILENAME)
        self.assertTrue(by_plat["android"].filename.endswith(".apk"))
        self.assertEqual(by_plat["android"].filename, ANDROID_APK_FILENAME)
        self.assertTrue(by_plat["macos"].filename.endswith(".zip"))
        self.assertEqual(by_plat["macos"].filename, MACOS_ZIP_FILENAME)
        self.assertTrue(by_plat["ios"].filename.endswith(".zip"))
        self.assertEqual(by_plat["ios"].filename, IOS_ZIP_FILENAME)

    def test_linux_button_label_simplified(self):
        """Linux download button text is short and exact."""
        assets = available_downloads()
        by_plat = {a.platform: a for a in assets}
        self.assertEqual(by_plat["linux"].label, "Linux - Installer (.tar.gz)")
        html = render_download_section_html()
        self.assertIn("Linux - Installer (.tar.gz)", html)
        self.assertIn('id="dl-linux"', html)
        self.assertEqual(
            by_plat["windows"].label, "Windows (x64) - Installer (.exe)"
        )
        self.assertEqual(by_plat["android"].label, "Android - APK installer")
        self.assertEqual(by_plat["macos"].label, "macOS - App package (.zip)")
        self.assertEqual(by_plat["ios"].label, "iOS - App package (.zip)")
        for name in (
            WINDOWS_EXE_FILENAME,
            ANDROID_APK_FILENAME,
            MACOS_ZIP_FILENAME,
            IOS_ZIP_FILENAME,
        ):
            self.assertIn(RELEASE_VERSION, name)

    def test_available_downloads_have_https_github_release_urls(self):
        assets = available_downloads()
        for a in assets:
            self.assertTrue(a.url.startswith("https://"))
            self.assertIn(f"/releases/download/{RELEASE_TAG}/", a.url)
            self.assertIn(a.filename, a.url)
            self.assertIn(RELEASE_VERSION, a.filename)
            expected = (
                f"https://github.com/rgsneddon/restore-privacy/releases/download/"
                f"{RELEASE_TAG}/{a.filename}"
            )
            self.assertEqual(a.url, expected)

    def test_render_download_section_uses_real_urls(self):
        html = render_download_section_html()
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertIn('class="dl"', html)
        self.assertIn("Windows", html)
        self.assertIn("Android", html)
        self.assertIn("macOS", html)
        self.assertIn("iOS", html)
        self.assertIn(".exe", html)
        self.assertIn(".apk", html)
        self.assertIn(".zip", html)
        for a in available_downloads():
            self.assertIn(a.url, html)
            self.assertNotIn('href="#"', html)

    def test_status_page_html_includes_downloads(self):
        """Public page keeps title + count and shows all platform download buttons."""
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 2}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", page)
        self.assertIn("clients-connected", page)
        self.assertIn("fetch('/api/status'", page)
        self.assertIn(f"Download client v{RELEASE_VERSION}", page)
        self.assertIn(f"releases/download/{RELEASE_TAG}/", page)
        self.assertIn(WINDOWS_EXE_FILENAME, page)
        self.assertIn(ANDROID_APK_FILENAME, page)
        self.assertIn(MACOS_ZIP_FILENAME, page)
        self.assertIn(IOS_ZIP_FILENAME, page)
        for a in available_downloads():
            self.assertIn(a.url, page)
        self.assertNotIn("windows-x64.zip", page)
        self.assertNotIn("windows-standalone", page)


class TestInstallerPackagingRecipe(unittest.TestCase):
    """Structural: current-tag build recipe produces advertised package names."""

    def test_build_script_wires_all_platform_names(self):
        script = (ROOT / "scripts" / f"build_release_{RELEASE_VERSION}.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'VERSION = "{RELEASE_VERSION}"', script)
        self.assertIn("windows-x64-setup.exe", script)
        self.assertIn("android.apk", script)
        self.assertIn("macos.zip", script)
        self.assertIn("ios.zip", script)
        self.assertIn("WINDOWS_EXE_NAME", script)
        self.assertIn("ANDROID_APK_NAME", script)
        self.assertIn("MACOS_ZIP_NAME", script)
        self.assertIn("IOS_ZIP_NAME", script)
        self.assertIn("package_macos_zip", script)
        self.assertIn("package_ios_zip", script)
        self.assertEqual(
            WINDOWS_EXE_FILENAME,
            f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe",
        )
        self.assertEqual(
            ANDROID_APK_FILENAME,
            f"restore-privacy-client-{RELEASE_VERSION}-android.apk",
        )
        self.assertEqual(
            MACOS_ZIP_FILENAME,
            f"restore-privacy-client-{RELEASE_VERSION}-macos.zip",
        )
        self.assertEqual(
            IOS_ZIP_FILENAME,
            f"restore-privacy-client-{RELEASE_VERSION}-ios.zip",
        )

    def test_installer_module_version(self):
        inst = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn(f'VERSION = "{RELEASE_VERSION}"', inst)
        self.assertIn("def install", inst)


if __name__ == "__main__":
    unittest.main()
