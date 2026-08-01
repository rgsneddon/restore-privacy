"""Rx Privacy Browser multi-platform packages: valid expand + inventory."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))


class TestRxPlatformMatrix(unittest.TestCase):
    def test_matrix_includes_all_platforms(self) -> None:
        from package_browser_rx import platform_package_matrix

        rows = platform_package_matrix("1.0.2")
        plats = {r["platform"] for r in rows}
        for need in (
            "macos",
            "windows",
            "linux-x86_64",
            "linux-aarch64",
            "ios",
            "android",
            "default",
            "chromium",
        ):
            self.assertIn(need, plats, msg=need)
        # Filenames contain platform token where applicable
        by = {r["platform"]: r for r in rows}
        self.assertIn("macos", by["macos"]["filename"])
        self.assertIn("windows", by["windows"]["filename"])
        self.assertTrue(by["linux-x86_64"]["filename"].endswith(".tar.gz"))
        self.assertTrue(by["default"]["filename"].endswith(".zip"))

    def test_package_produces_valid_expandable_zips(self) -> None:
        from package_browser_rx import package, validate_archive, platform_package_matrix

        with tempfile.TemporaryDirectory() as td:
            # package writes to releases/ — use real package then validate matrix paths
            # Drive package_one into temp via monkeypatching would skip assets mirror;
            # call package() which uses monorepo releases (side effect ok for pin).
            paths = package(version="1.0.2")
            self.assertGreaterEqual(len(paths), 8)
            for p in paths:
                self.assertTrue(p.is_file(), p)
                self.assertGreater(p.stat().st_size, 500)
                validate_archive(p)
                if p.suffix == ".zip" or p.name.endswith(".zip"):
                    # PK magic
                    self.assertEqual(p.read_bytes()[:2], b"PK")
                    with zipfile.ZipFile(p, "r") as zf:
                        names = zf.namelist()
                        self.assertTrue(
                            any(n.endswith("manifest.json") for n in names),
                            msg=p.name,
                        )
                        self.assertTrue(
                            any("INSTALL.md" in n for n in names),
                            msg=p.name,
                        )
                        # Must not be a single HTML 404 body
                        self.assertNotEqual(zf.read(names[0])[:9], b"not found")


class TestRxDownloadHrefs(unittest.TestCase):
    def test_device_aware_hrefs_and_free_open(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            list_rx_browser_platform_packages,
            rx_browser_package_filename,
            rx_browser_package_href,
        )
        from payments import free_open_filenames

        self.assertEqual(RELEASE_VERSION, "1.0.2")
        mac = rx_browser_package_href(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        self.assertIn("macos", mac)
        self.assertIn("/assets/1.0.2/", mac)
        win = rx_browser_package_href(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        self.assertIn("windows", win)
        default = rx_browser_package_href()
        self.assertTrue(default.endswith(f"restore-privacy-rx-browser-{RELEASE_VERSION}.zip"))

        names = free_open_filenames()
        for row in list_rx_browser_platform_packages():
            self.assertIn(row["filename"], names, msg=row["filename"])
            self.assertIn(RELEASE_VERSION, row["relative_path"])

        self.assertEqual(
            rx_browser_package_filename(platform="macos"),
            f"restore-privacy-rx-browser-{RELEASE_VERSION}-macos.zip",
        )


if __name__ == "__main__":
    unittest.main()
