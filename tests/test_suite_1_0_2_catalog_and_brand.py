"""Suite 1.0.2 catalog pin + brand installer presence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestSuite102Catalog(unittest.TestCase):
    def test_catalog_pin_is_1_0_2(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            FREE_DOWNLOAD_FACE_VERSION,
            WINDOWS_EXE_FILENAME,
            ANDROID_APK_FILENAME,
            MACOS_ZIP_FILENAME,
            IOS_ZIP_FILENAME,
            LINUX_TGZ_FILENAME,
            list_catalog_platform_packages,
            render_download_section_html,
        )

        self.assertEqual(RELEASE_VERSION, "1.0.2")
        self.assertEqual(FREE_DOWNLOAD_FACE_VERSION, "1.0.2")
        for name in (
            WINDOWS_EXE_FILENAME,
            ANDROID_APK_FILENAME,
            MACOS_ZIP_FILENAME,
            IOS_ZIP_FILENAME,
            LINUX_TGZ_FILENAME,
        ):
            self.assertIn("1.0.2", name)
            self.assertNotIn("1.0.1", name)
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        self.assertTrue(all(p["version"] == "1.0.2" for p in pkgs))
        html = render_download_section_html()
        self.assertIn("1.0.2", html)
        from public_chrome import PUBLIC_BRAND_VERSION, PUBLIC_BRAND_DISPLAY
        self.assertEqual(PUBLIC_BRAND_VERSION, "1.0.2")
        self.assertIn("1.0.2", PUBLIC_BRAND_DISPLAY)
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn('data-suite-version="{RELEASE_VERSION}"', app_src)

    def test_release_files_present(self) -> None:
        d = ROOT / "releases" / "1.0.2"
        for plat, name in (
            ("windows", "restore-privacy-client-1.0.2-windows-x64-setup.exe"),
            ("android", "restore-privacy-client-1.0.2-android.apk"),
            ("macos", "restore-privacy-client-1.0.2-macos.zip"),
            ("ios", "restore-privacy-client-1.0.2-ios.zip"),
            ("linux", "restore-privacy-client-1.0.2-linux-x64.tar.gz"),
        ):
            p = d / name
            self.assertTrue(p.is_file(), p)
            self.assertGreater(p.stat().st_size, 1000)


class TestBrand102Inventory(unittest.TestCase):
    def test_brand_inventory_includes_all_products(self) -> None:
        from brand_package_inventory import inventory_with_presence

        inv = inventory_with_presence(suite_version="1.0.2", repo_root=ROOT)
        self.assertTrue(inv.get("ok"))
        self.assertGreaterEqual(int(inv["present_count"]), 20)
        kinds = set(inv.get("kinds") or [])
        for k in (
            "suite_client",
            "browser",
            "rpos",
            "rpos_app",
            "rpmail",
            "rpoffice",
        ):
            self.assertIn(k, kinds)
        # Suite pin in client filenames
        suite = [p for p in inv["packages"] if p["kind"] == "suite_client"]
        self.assertEqual(len(suite), 5)
        self.assertTrue(all("1.0.2" in p["filename"] for p in suite))


if __name__ == "__main__":
    unittest.main()
