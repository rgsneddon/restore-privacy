"""Upgrade recommend must not surface undeployed / phantom monopin."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestCatalogRecommendHonesty(unittest.TestCase):
    def setUp(self) -> None:
        import client.ui_theme as ut

        ut._REMOTE_CATALOG_FETCHED = False
        ut._REMOTE_CATALOG_VERSION_CACHE = None
        ut._REMOTE_CATALOG_INFO_CACHE = None

    def tearDown(self) -> None:
        import client.ui_theme as ut

        ut._REMOTE_CATALOG_FETCHED = False
        ut._REMOTE_CATALOG_VERSION_CACHE = None
        ut._REMOTE_CATALOG_INFO_CACHE = None

    def test_phantom_remote_ahead_without_windows_ready_stays_local(self) -> None:
        """Remote 1.1.10 without windows_ready must not become 'latest' on Windows."""
        from client import ui_theme as ut

        with mock.patch.object(
            ut,
            "fetch_remote_catalog_info",
            return_value={
                "catalog_version": "1.1.10",
                "platforms_ready": {
                    "android": True,
                    "macos": True,
                    "ios": True,
                    "linux": True,
                    "windows": False,
                },
                "windows_ready": False,
            },
        ), mock.patch.object(
            ut, "embedded_package_version", return_value="1.2.0"
        ), mock.patch.object(
            ut, "local_catalog_version", return_value="1.2.0"
        ), mock.patch.object(
            ut, "client_platform_key", return_value="windows"
        ):
            latest = ut.catalog_latest_version(prefer_remote=True)
            self.assertEqual(latest, "1.2.0")
            self.assertFalse(
                ut.upgrade_available(running="1.2.0", latest=latest)
            )
            self.assertIsNone(
                ut.upgrade_banner_text(running="1.2.0", latest=latest)
            )

    def test_remote_ahead_with_windows_ready_allows_upgrade(self) -> None:
        from client import ui_theme as ut

        with mock.patch.object(
            ut,
            "fetch_remote_catalog_info",
            return_value={
                "catalog_version": "1.1.11",
                "platforms_ready": {"windows": True},
                "windows_ready": True,
            },
        ), mock.patch.object(
            ut, "embedded_package_version", return_value="1.2.0"
        ), mock.patch.object(
            ut, "local_catalog_version", return_value="1.2.0"
        ), mock.patch.object(
            ut, "client_platform_key", return_value="windows"
        ):
            latest = ut.catalog_latest_version(prefer_remote=True)
            self.assertEqual(latest, "1.1.11")
            self.assertTrue(ut.upgrade_available(running="1.2.0", latest=latest))

    def test_legacy_api_remote_ahead_no_ready_field_no_phantom_upgrade(self) -> None:
        """Legacy API (only catalog_version) ahead of emb → do not recommend."""
        from client import ui_theme as ut

        with mock.patch.object(
            ut,
            "fetch_remote_catalog_info",
            return_value={"catalog_version": "1.1.10"},
        ), mock.patch.object(
            ut, "embedded_package_version", return_value="1.2.0"
        ), mock.patch.object(
            ut, "local_catalog_version", return_value="1.2.0"
        ), mock.patch.object(
            ut, "client_platform_key", return_value="windows"
        ):
            latest = ut.catalog_latest_version(prefer_remote=True)
            self.assertEqual(latest, "1.2.0")
            self.assertFalse(ut.upgrade_available(running="1.2.0"))

    def test_monopin_stays_1_2_0(self) -> None:
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "1.2.0")
        from status_page.downloads import RELEASE_VERSION, RELEASE_TAG

        self.assertEqual(RELEASE_VERSION, "1.2.0")
        self.assertEqual(RELEASE_TAG, "1.2.0")

    def test_remote_catalog_platform_ready_helper(self) -> None:
        from client.ui_theme import remote_catalog_platform_ready

        self.assertIsNone(remote_catalog_platform_ready(None))
        self.assertTrue(
            remote_catalog_platform_ready(
                {"windows_ready": True}, platform="windows"
            )
        )
        self.assertFalse(
            remote_catalog_platform_ready(
                {"platforms_ready": {"windows": False}}, platform="windows"
            )
        )


if __name__ == "__main__":
    unittest.main()
