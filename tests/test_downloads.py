"""Tests for shipped status-page download catalog (release 0.0.2)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    ANDROID_APK_FILENAME,
    RELEASE_TAG,
    RELEASE_VERSION,
    WINDOWS_EXE_FILENAME,
    available_downloads,
    render_download_section_html,
)


class TestDownloadCatalog(unittest.TestCase):
    def test_version_is_0_0_2(self):
        self.assertEqual(RELEASE_VERSION, "0.0.2")
        self.assertEqual(RELEASE_TAG, "0.0.2")

    def test_public_assets_are_exe_and_apk_only(self):
        assets = available_downloads()
        self.assertEqual(len(assets), 2)
        platforms = {a.platform for a in assets}
        self.assertEqual(platforms, {"windows", "android"})
        by_plat = {a.platform: a for a in assets}
        self.assertTrue(by_plat["windows"].filename.endswith(".exe"))
        self.assertEqual(by_plat["windows"].filename, WINDOWS_EXE_FILENAME)
        self.assertTrue(by_plat["android"].filename.endswith(".apk"))
        self.assertEqual(by_plat["android"].filename, ANDROID_APK_FILENAME)
        self.assertIn("0.0.2", WINDOWS_EXE_FILENAME)
        self.assertIn("0.0.2", ANDROID_APK_FILENAME)

    def test_available_downloads_have_https_github_release_urls(self):
        assets = available_downloads()
        for a in assets:
            self.assertTrue(a.url.startswith("https://"))
            self.assertIn("/releases/download/0.0.2/", a.url)
            self.assertIn(a.filename, a.url)
            self.assertIn("0.0.2", a.filename)
            # URLs come from shipped DownloadAsset.url property, not test-only strings
            expected = (
                f"https://github.com/rgsneddon/restore-privacy/releases/download/"
                f"0.0.2/{a.filename}"
            )
            self.assertEqual(a.url, expected)

    def test_render_download_section_uses_real_urls(self):
        html = render_download_section_html()
        self.assertIn("Download client v0.0.2", html)
        self.assertIn('class="dl"', html)
        self.assertIn("Windows", html)
        self.assertIn("Android", html)
        self.assertIn(".exe", html)
        self.assertIn(".apk", html)
        for a in available_downloads():
            self.assertIn(a.url, html)
            self.assertNotIn('href="#"', html)

    def test_status_page_html_includes_downloads(self):
        """Public page keeps title + count and shows .exe + .apk buttons."""
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 2}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", page)
        self.assertIn("clients-connected", page)
        self.assertIn("fetch('/api/status'", page)
        self.assertIn("Download client v0.0.2", page)
        self.assertIn("releases/download/0.0.2/", page)
        self.assertIn(WINDOWS_EXE_FILENAME, page)
        self.assertIn(ANDROID_APK_FILENAME, page)
        # Catalog-built URLs appear in page
        for a in available_downloads():
            self.assertIn(a.url, page)
        # No old zip-only packaging advertised as primary
        self.assertNotIn("windows-x64.zip", page)
        self.assertNotIn("windows-standalone", page)


class TestInstallerPackagingRecipe(unittest.TestCase):
    """Structural: 0.0.2 build recipe produces the advertised setup .exe name."""

    def test_build_script_wires_exe_and_apk_names(self):
        script = (ROOT / "scripts" / "build_release_0.0.2.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.0.2"', script)
        # Filenames are composed from VERSION in the shipped build script
        self.assertIn("windows-x64-setup.exe", script)
        self.assertIn("android.apk", script)
        self.assertIn("WINDOWS_EXE_NAME", script)
        self.assertIn("ANDROID_APK_NAME", script)
        self.assertIn("installer.py", script)
        self.assertIn("PyInstaller", script)
        self.assertIn("build_windows_installer_exe", script)
        self.assertIn("onefile", script)
        self.assertIn("payload", script)
        # Catalog and build script agree on the public names
        self.assertEqual(
            WINDOWS_EXE_FILENAME,
            f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe",
        )
        self.assertEqual(
            ANDROID_APK_FILENAME,
            f"restore-privacy-client-{RELEASE_VERSION}-android.apk",
        )

    def test_installer_module_deploys_and_launches(self):
        inst = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("VERSION = \"0.0.2\"", inst)
        self.assertIn("def install", inst)
        self.assertIn("LOCALAPPDATA", inst)
        self.assertIn("Programs", inst)
        self.assertIn("subprocess.Popen", inst)
        self.assertIn("_payload_root", inst)


if __name__ == "__main__":
    unittest.main()
