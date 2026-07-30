"""New version available wiring on all five paid VPN client surfaces."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestUpgradeHelpers(unittest.TestCase):
    def test_banner_wording_new_version_available(self):
        from client.ui_theme import upgrade_available, upgrade_banner_text

        msg = upgrade_banner_text(running="0.4.10", latest="0.5.0")
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("New version available", msg)
        self.assertIn("0.4.10", msg)
        self.assertIn("0.5.0", msg)
        self.assertTrue(upgrade_available(running="0.4.10", latest="0.5.0"))
        self.assertFalse(upgrade_available(running="0.5.0", latest="0.5.0"))

    def test_upgrade_url_platform_monopin_download_not_pay(self):
        """Get update opens platform monopin upgrade-download — not /pay Checkout."""
        from client.ui_theme import (
            catalog_installer_filename,
            upgrade_download_url,
        )

        for plat in ("windows", "linux", "macos", "ios", "android"):
            url = upgrade_download_url(platform=plat)
            self.assertNotIn("releases/download", url)
            self.assertTrue(
                url.startswith("https://"),
                msg=f"{plat}: expected absolute https, got {url!r}",
            )
            self.assertIn("restoreprivacy.online", url)
            # Primary hop is upgrade-download or /download?token= — never /pay
            self.assertNotIn("/pay?", url, msg=f"{plat}: {url}")
            self.assertNotIn("/pay&", url)
            self.assertTrue(
                "/upgrade-download" in url or "/download?token=" in url,
                msg=f"{plat}: {url}",
            )
            self.assertIn(f"platform={plat}", url)
            fname = catalog_installer_filename(plat)
            self.assertIsNotNone(fname)
            self.assertIn(plat if plat != "windows" else "windows", fname or "")

    def test_upgrade_url_with_token_is_direct_download(self):
        from client.ui_theme import upgrade_download_url

        url = upgrade_download_url(platform="macos", token="testToken123")
        self.assertIn("/download?token=", url)
        self.assertNotIn("/pay", url)
        self.assertTrue(url.startswith("https://"))

    def test_upgrade_url_absolute_when_downloads_module_importable(self):
        """Preferred path: monopin upgrade-download still absolute https."""
        import importlib
        import sys

        root = str(ROOT)
        sp = str(ROOT / "status_page")
        for p in (root, sp):
            if p not in sys.path:
                sys.path.insert(0, p)
        import client.ui_theme as ui_theme

        importlib.reload(ui_theme)
        for plat in ("windows", "linux", "macos"):
            url = ui_theme.upgrade_download_url(platform=plat)
            self.assertTrue(url.startswith("https://"), msg=url)
            self.assertIn("restoreprivacy.online", url)
            self.assertIn("/upgrade-download", url)
            self.assertIn(f"platform={plat}", url)
            self.assertNotIn("/pay?", url)
            self.assertFalse(url.startswith("/"))

    def test_upgrade_surfaces_lists_all_five_platforms(self):
        from client.ui_theme import upgrade_surfaces

        surfaces = upgrade_surfaces()
        for plat in ("windows", "linux", "macos", "ios", "android"):
            self.assertIn(plat, surfaces)
            self.assertTrue(surfaces[plat])


class TestPlatformWiringStructural(unittest.TestCase):
    def test_windows_and_linux_call_shared_banner(self):
        win = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        linux = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        for src, name in ((win, "windows"), (linux, "linux")):
            self.assertIn("upgrade_banner_text", src, name)
            self.assertIn("upgrade_download_url", src, name)
            self.assertIn("_open_upgrade", src, name)

    def test_flutter_shells_wire_upgrade_banner(self):
        """macOS / iOS / Android residual UI is Flutter main + upgrade_banner.dart."""
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        banner = (ROOT / "client_app" / "lib" / "upgrade_banner.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("upgrade_banner.dart", main)
        self.assertIn("UpgradeBanner", main)
        self.assertIn("New version available", banner)
        self.assertIn("versionIsBehind", banner)
        self.assertIn("upgradeDownloadUrl", banner)
        self.assertIn("/api/catalog-version", banner)
        self.assertIn("Get update", banner)
        # Paid path only
        self.assertNotIn("github.com", banner.lower())
        self.assertIn("restoreprivacy.online", banner)

    def test_android_uses_flutter_main_shell(self):
        # Residual Android is the Flutter Runner — same UpgradeBanner
        android_main = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
        )
        self.assertTrue(android_main.is_dir())
        # Flutter entry is always client_app/lib/main.dart for residual Android UI
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("UpgradeBanner", main)


class TestRemoteCatalogOptional(unittest.TestCase):
    def test_fetch_remote_catalog_mocked(self):
        from client import ui_theme

        class _Resp:
            def read(self):
                return b'{"catalog_version":"0.9.9","downloads_url":"https://x/#downloads"}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        # Isolate cache for this test
        prev_fetched = ui_theme._REMOTE_CATALOG_FETCHED
        prev_cache = ui_theme._REMOTE_CATALOG_VERSION_CACHE
        try:
            ui_theme._REMOTE_CATALOG_FETCHED = False
            ui_theme._REMOTE_CATALOG_VERSION_CACHE = None
            with mock.patch("urllib.request.urlopen", return_value=_Resp()):
                v = ui_theme.fetch_remote_catalog_version(force=True)
            self.assertEqual(v, "0.9.9")
            self.assertEqual(ui_theme.catalog_latest_version(prefer_remote=True), "0.9.9")
            self.assertTrue(ui_theme.upgrade_available(running="0.5.0", latest="0.9.9"))
        finally:
            ui_theme._REMOTE_CATALOG_FETCHED = prev_fetched
            ui_theme._REMOTE_CATALOG_VERSION_CACHE = prev_cache


if __name__ == "__main__":
    unittest.main()
