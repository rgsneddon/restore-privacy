"""Running version must not fall back to 0.0.0; upgrade banner only when behind."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client import ui_theme  # noqa: E402
from client.ui_theme import (  # noqa: E402
    catalog_latest_version,
    embedded_package_version,
    read_running_version,
    upgrade_available,
    upgrade_banner_text,
    upgrade_download_url,
    version_file_candidates,
)


class TestVersionResolution(unittest.TestCase):
    def test_repo_client_version_is_readable(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(ver, r"^\d+\.\d+")
        self.assertEqual(read_running_version(), ver)
        self.assertNotEqual(read_running_version(), "0.0.0")
        # Current ship pin (not a stale prior release)
        self.assertRegex(ver, r"^0\.(3|4|5)\.\d+$")
        self.assertNotEqual(read_running_version(), "0.2.3")
        # Prefer local catalog when comparing monorepo pins (remote may lag/env)
        from client.ui_theme import catalog_latest_version as cat

        self.assertEqual(ver, cat(prefer_remote=False))

    def test_stale_version_file_does_not_override_newer_package_pin(self):
        """Leftover 0.2.3 VERSION must not win over package 0.3.4 pin."""
        with tempfile.TemporaryDirectory() as td:
            stale = Path(td) / "old" / "VERSION"
            stale.parent.mkdir(parents=True)
            stale.write_text("0.2.3\n", encoding="utf-8")
            fresh = Path(td) / "package" / "VERSION"
            fresh.parent.mkdir(parents=True)
            fresh.write_text("0.3.4\n", encoding="utf-8")
            with mock.patch.object(
                ui_theme,
                "version_file_candidates",
                return_value=[stale, fresh],
            ):
                with mock.patch.object(
                    ui_theme, "embedded_package_version", return_value="0.3.4"
                ):
                    self.assertEqual(read_running_version(), "0.3.4")
                    self.assertNotEqual(read_running_version(), "0.2.3")

    def test_install_dir_version_readable_when_only_source(self):
        """Simulates frozen: VERSION only at install root."""
        with tempfile.TemporaryDirectory() as td:
            install = Path(td)
            (install / "VERSION").write_text("0.1.8\n", encoding="utf-8")
            with mock.patch.object(
                ui_theme,
                "version_file_candidates",
                return_value=[install / "VERSION", Path(td) / "missing" / "VERSION"],
            ):
                with mock.patch.object(
                    ui_theme, "embedded_package_version", return_value="0.1.8"
                ):
                    self.assertEqual(read_running_version(), "0.1.8")

    def test_explicit_version_file(self):
        with tempfile.TemporaryDirectory() as td:
            vf = Path(td) / "VERSION"
            vf.write_text("0.9.9\n", encoding="utf-8")
            self.assertEqual(read_running_version(vf), "0.9.9")

    def test_candidates_include_install_and_frozen_shapes(self):
        cands = version_file_candidates()
        joined = "\n".join(str(p) for p in cands)
        self.assertIn("VERSION", joined)
        self.assertTrue(any(p.name == "VERSION" for p in cands))

    def test_embedded_package_version_not_zero(self):
        self.assertNotEqual(embedded_package_version(), "0.0.0")
        self.assertRegex(embedded_package_version(), r"^\d+\.\d+")
        self.assertEqual(
            embedded_package_version(),
            catalog_latest_version(prefer_remote=False),
        )

    def test_all_product_pins_match_monorepo(self):
        """Windows installer, catalog, Flutter pubspec/RptConfig share client/VERSION."""
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        # Local monorepo pin (ignore remote cache from other tests)
        self.assertEqual(pin, catalog_latest_version(prefer_remote=False))
        # Installer loads pin from client/VERSION
        from client.windows import installer as inst

        self.assertEqual(inst.VERSION, pin)
        pubspec = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn(f"version: {pin}+", pubspec)
        rpt = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"productVersion = '{pin}'", rpt)
        # UI surfaces call the real helpers
        win = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        linux = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("read_running_version", win)
        self.assertIn("read_running_version", linux)
        flutter_main = (ROOT / "client_app" / "lib" / "main.dart").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            "RptConfig.productVersion" in flutter_main
            or "RptConfig.displayProductVersion" in flutter_main
            or "productVersion" in flutter_main,
            "Flutter main must surface product version monopin",
        )


class TestUpgradeBanner(unittest.TestCase):
    def test_no_banner_when_current_equals_catalog(self):
        latest = catalog_latest_version()
        self.assertIsNone(upgrade_banner_text(running=latest, latest=latest))
        self.assertFalse(upgrade_available(running=latest, latest=latest))

    def test_banner_when_behind(self):
        msg = upgrade_banner_text(running="0.1.0", latest="0.1.8")
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("New version available", msg)
        self.assertIn("0.1.0", msg)
        self.assertIn("0.1.8", msg)
        self.assertNotIn("0.0.0", msg)
        self.assertTrue(upgrade_available(running="0.1.0", latest="0.1.8"))

    def test_zero_placeholder_does_not_force_upgrade_against_self(self):
        """If something still returns 0.0.0, treat as embedded package version."""
        emb = embedded_package_version()
        # Equal after normalization → no banner
        self.assertFalse(upgrade_available(running="0.0.0", latest=emb))
        self.assertIsNone(upgrade_banner_text(running="0.0.0", latest=emb))

    def test_app_wires_banner_only_when_message(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("upgrade_banner_text", src)
        self.assertIn("if self._upgrade_msg", src)
        self.assertIn("upgrade_frame.pack", src)

    def test_upgrade_download_url_is_monopin_not_pay_or_free_github(self):
        """In-app update opens monopin installer path; never free GH or /pay."""
        url = upgrade_download_url()
        self.assertTrue(isinstance(url, str) and len(url) > 0)
        self.assertNotIn("releases/download", url)
        self.assertNotIn("releases/latest", url)
        self.assertTrue(
            url.startswith("https://"),
            msg=f"expected absolute https upgrade url: {url!r}",
        )
        self.assertNotIn("/pay?", url)
        self.assertIn("restoreprivacy.online", url)
        self.assertTrue(
            "/upgrade-download" in url or "/download?token=" in url,
            msg=f"unexpected upgrade url: {url}",
        )


if __name__ == "__main__":
    unittest.main()
