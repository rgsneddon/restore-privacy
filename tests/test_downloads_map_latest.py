"""Downloads Map is the live version source of truth (per-platform latest)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestDownloadsMapLatest(unittest.TestCase):
    def test_map_file_lists_windows_125_and_others(self) -> None:
        from downloads import (
            downloads_map_path,
            load_downloads_map_public,
            map_platform_filename,
            map_platform_version,
        )

        self.assertTrue(downloads_map_path().is_file())
        pub = load_downloads_map_public()
        for plat in ("windows", "android", "macos", "ios", "linux"):
            ver = map_platform_version(plat)
            fname = map_platform_filename(plat)
            self.assertTrue(ver, f"empty map version for {plat}")
            self.assertIn(ver, fname)
            self.assertEqual(pub["platforms"][plat]["version"], ver)
            self.assertEqual(pub["platforms"][plat]["filename"], fname)
        self.assertEqual(map_platform_version("linux"), "1.2.6")
        self.assertIn("1.2.6", map_platform_filename("linux"))
        self.assertEqual(map_platform_version("windows"), "1.2.6")

    def test_fulfilment_and_host_delivery_watch_map(self) -> None:
        from downloads import map_platform_filename, map_platform_version
        from host_delivery import safe_catalog_version_and_filename
        from payments import platform_filename, vps_asset_url

        win = map_platform_filename("windows")
        win_ver = map_platform_version("windows")
        self.assertEqual(platform_filename("windows"), win)
        pair = safe_catalog_version_and_filename(win)
        self.assertIsNotNone(pair)
        assert pair is not None
        self.assertEqual(pair[0], win_ver)
        self.assertEqual(pair[1], win)
        url = vps_asset_url(win)
        self.assertIn(f"/{win_ver}/", url)
        self.assertTrue(url.endswith(win))
        linux_ver = map_platform_version("linux")
        self.assertEqual(linux_ver, "1.2.6")
        linux = map_platform_filename("linux")
        self.assertIn(f"/{linux_ver}/", vps_asset_url(linux))

    def test_ned_snapshot_includes_downloads_map(self) -> None:
        from admin_rps import ned_growth_public_snapshot
        from downloads import map_platform_version
        from node.oracle_master import ned_learn_oracle

        snap = ned_growth_public_snapshot({})
        self.assertIn("downloads_map", snap)
        win_ver = snap["downloads_map"]["platforms"]["windows"]["version"]
        linux_ver = snap["downloads_map"]["platforms"]["linux"]["version"]
        self.assertEqual(win_ver, map_platform_version("windows"))
        self.assertEqual(linux_ver, "1.2.6")
        learned = ned_learn_oracle(
            {"learning_epochs": 0},
            {"downloads_map": snap["downloads_map"]},
        )
        self.assertTrue(learned.get("downloads_map_learned"))
        self.assertEqual(
            learned["downloads_map"]["platforms"]["windows"]["version"], win_ver
        )
        self.assertEqual(
            learned["downloads_map"]["platforms"]["linux"]["version"], "1.2.6"
        )
        self.assertGreaterEqual(int(learned.get("learning_epochs") or 0), 1)

    def test_map_json_round_trip_shape(self) -> None:
        from downloads import downloads_map_path, load_downloads_map_public

        raw = json.loads(downloads_map_path().read_text(encoding="utf-8"))
        pub = load_downloads_map_public()
        self.assertEqual(
            raw["platforms"]["windows"]["filename"],
            pub["platforms"]["windows"]["filename"],
        )

    def test_static_downloads_map_page_uses_live_map_pins(self) -> None:
        from downloads import map_platform_version

        html = (ROOT / "public_site" / "downloads-map.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-downloads-map-page", html)
        self.assertNotIn("v1.2.4", html)
        self.assertNotIn("v1.2.5", html)
        for plat, face in (
            ("windows", "Windows"),
            ("android", "Android"),
            ("macos", "macOS"),
            ("ios", "iOS"),
            ("linux", "Linux"),
        ):
            ver = map_platform_version(plat)
            self.assertIn(f"{face} - v{ver}", html)
            self.assertIn(f'data-platform="{plat}"', html)
        self.assertEqual(map_platform_version("linux"), "1.2.6")


if __name__ == "__main__":
    unittest.main()
