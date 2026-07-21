"""Restore Internet failsafe — sources, residual restore, uninstall, package membership."""

from __future__ import annotations

import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from client.restore_internet_failsafe import (  # noqa: E402
    PLATFORM_SOURCES,
    RESTORE_INTERNET_DISPLAY_NAME,
    assert_source_files_exist,
    inventory_packaging_sources,
    linux_residual_restore_markers,
    package_member_names_for_platform,
    windows_residual_restore_markers,
)

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
REL = ROOT / "releases" / VERSION


class TestRestoreInternetSources(unittest.TestCase):
    def test_all_platform_sources_exist(self):
        missing = assert_source_files_exist(ROOT)
        self.assertEqual(missing, [], msg=f"missing Restore Internet sources: {missing}")
        inv = inventory_packaging_sources(ROOT)
        for plat in ("windows", "linux", "macos", "ios", "android"):
            self.assertTrue(inv[plat], msg=plat)
            self.assertTrue(Path(inv[plat]).is_file())

    def test_windows_script_restores_and_removes(self):
        bat = ROOT / "client" / "windows" / "Restore Internet.bat"
        text = bat.read_text(encoding="utf-8", errors="replace")
        for m in windows_residual_restore_markers():
            self.assertIn(m, text, msg=m)
        self.assertIn("taskkill", text.lower())
        self.assertIn("rmdir", text.lower())
        self.assertIn(".restore-privacy", text)
        self.assertIn("RPT-FW", text)
        self.assertIn(RESTORE_INTERNET_DISPLAY_NAME, text)
        # Portable SFX tree (catalog extract) — not only LocalAppData install
        self.assertIn("%~dp0RestorePrivacy.exe", text)
        self.assertIn("Remove-Item -LiteralPath", text)
        # Must not use broken escaped quotes in delayed delete
        self.assertNotIn('\\"%INSTALL%\\"', text)
        self.assertNotIn('rmdir /s /q \\"', text)

    def test_linux_script_restores_and_removes(self):
        sh = ROOT / "client" / "linux" / "Restore Internet"
        text = sh.read_text(encoding="utf-8")
        for m in linux_residual_restore_markers():
            self.assertIn(m, text, msg=m)
        self.assertIn("pkill", text)
        self.assertTrue(sh.stat().st_mode & 0o111, "linux script must be executable")

    def test_macos_and_mobile_docs(self):
        mac = (ROOT / "client_app" / "macos" / "Restore Internet.command").read_text(
            encoding="utf-8"
        )
        self.assertIn("restore_privacy_client.app", mac)
        self.assertIn(".restore-privacy", mac)
        self.assertIn("VPN", mac)
        ios = (ROOT / "client_app" / "ios" / "Restore Internet.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("Settings", ios)
        self.assertIn("VPN", ios)
        andr = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "assets"
            / "Restore Internet.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("Uninstall", andr)
        self.assertIn("VPN", andr)


class TestRestoreInternetInCatalogPackages(unittest.TestCase):
    def test_inventory_each_catalog_package(self):
        """Each monopin installer embeds a Restore Internet artifact."""
        if not REL.is_dir():
            self.skipTest("no releases tree")
        report: list[str] = []
        for plat, suffix in (
            ("windows", "windows-x64-setup.exe"),
            ("linux", "linux-x64.tar.gz"),
            ("macos", "macos.zip"),
            ("ios", "ios.zip"),
            ("android", "android.apk"),
        ):
            fname = f"restore-privacy-client-{VERSION}-{suffix}"
            path = REL / fname
            self.assertTrue(path.is_file(), f"missing {fname}")
            names = package_member_names_for_platform(plat)
            found = self._package_has_any(path, names)
            report.append(f"{plat}: {fname} -> {found}")
            self.assertTrue(
                found,
                msg=f"{plat} package missing Restore Internet members {names}",
            )
        # Durable inventory for scratch capture in CI/local
        inv_path = ROOT / "releases" / VERSION / "RESTORE_INTERNET_INVENTORY.txt"
        # Do not require writing to releases (may be large); keep assertion only
        self.assertEqual(len(report), 5)

    def _package_has_any(self, path: Path, needles: tuple[str, ...]) -> bool:
        nlow = path.name.lower()
        if nlow.endswith((".zip", ".apk")):
            with zipfile.ZipFile(path) as zf:
                members = zf.namelist()
            joined = "\n".join(members)
            return any(n in joined for n in needles)
        if nlow.endswith((".tar.gz", ".tgz")):
            with tarfile.open(path, "r:gz") as tf:
                members = tf.getnames()
            joined = "\n".join(members)
            return any(n in joined for n in needles)
        if nlow.endswith(".exe"):
            r = subprocess.run(
                ["7z", "l", str(path)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = r.stdout or ""
            return any(n in out for n in needles)
        return False

    def test_windows_package_is_pe_and_has_restore_internet(self):
        path = REL / f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
        if not path.is_file():
            self.skipTest("windows package missing")
        self.assertEqual(path.read_bytes()[:2], b"MZ")
        r = subprocess.run(
            ["7z", "l", str(path)], capture_output=True, text=True, timeout=60
        )
        self.assertIn("Restore Internet.bat", r.stdout)


class TestInstallerWiresRestoreInternet(unittest.TestCase):
    def test_windows_installer_ships_failsafe_shortcut(self):
        inst = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("Restore Internet.bat", inst)
        self.assertIn("Restore Internet.lnk", inst)
        self.assertIn("Uninstall.bat", inst)

    def test_package_linux_writes_failsafe(self):
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("write_restore_internet", src)
        self.assertIn("Restore Internet", src)


if __name__ == "__main__":
    unittest.main()
