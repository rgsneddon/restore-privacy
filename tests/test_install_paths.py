"""Default install roots (Program Files) + client/Restore Internet bundle inventory."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.install_paths import (  # noqa: E402
    PRODUCT_FOLDER_DISPLAY,
    PRODUCT_FOLDER_LEGACY_ID,
    default_install_dir_for_platform,
    default_linux_install_dir,
    default_macos_install_dir,
    default_windows_install_dir,
    inventory_install_bundle,
    is_under_program_files,
    per_user_windows_install_dir,
    planned_windows_bundle_entries,
    windows_program_files_root,
)


class TestWindowsInstallPaths(unittest.TestCase):
    def test_default_under_program_files_restore_privacy(self):
        env = {
            "ProgramFiles": r"C:\Program Files",
            "LOCALAPPDATA": r"C:\Users\test\AppData\Local",
        }
        d = default_windows_install_dir(env)
        self.assertEqual(d, Path(r"C:\Program Files") / PRODUCT_FOLDER_DISPLAY)
        self.assertTrue(is_under_program_files(d, env))
        self.assertIn("Program Files", str(d))
        self.assertIn("Restore Privacy", str(d))

    def test_program_files_x86_when_env_set(self):
        env = {"ProgramFiles(x86)": r"C:\Program Files (x86)"}
        root = windows_program_files_root(env, prefer_x86=True)
        self.assertEqual(root, Path(r"C:\Program Files (x86)"))

    def test_rpt_install_dir_override(self):
        env = {
            "ProgramFiles": r"C:\Program Files",
            "RPT_INSTALL_DIR": r"D:\Custom\RestorePrivacy",
        }
        self.assertEqual(
            default_windows_install_dir(env),
            Path(r"D:\Custom\RestorePrivacy"),
        )

    def test_per_user_opt_in(self):
        env = {
            "ProgramFiles": r"C:\Program Files",
            "LOCALAPPDATA": r"C:\Users\test\AppData\Local",
            "RPT_INSTALL_PER_USER": "1",
        }
        d = default_windows_install_dir(env)
        self.assertEqual(
            d,
            Path(r"C:\Users\test\AppData\Local\Programs")
            / PRODUCT_FOLDER_LEGACY_ID,
        )
        self.assertFalse(is_under_program_files(d, env))

    def test_legacy_localappdata_helper(self):
        env = {"LOCALAPPDATA": r"C:\Users\x\AppData\Local"}
        d = per_user_windows_install_dir(env)
        self.assertTrue(str(d).endswith(r"Programs\RestorePrivacy"))


class TestOtherPlatforms(unittest.TestCase):
    def test_linux_opt_restore_privacy(self):
        d = default_linux_install_dir({})
        self.assertEqual(d, Path("/opt/restore-privacy"))
        self.assertEqual(
            default_linux_install_dir({"PREFIX": "/usr/local"}),
            Path("/usr/local/restore-privacy"),
        )

    def test_macos_applications(self):
        d = default_macos_install_dir({})
        self.assertEqual(d, Path("/Applications") / "Restore Privacy.app")
        self.assertIn("Applications", str(d))

    def test_dispatch(self):
        env = {"ProgramFiles": r"C:\Program Files"}
        win = default_install_dir_for_platform("win32", env)
        self.assertEqual(win.name, "Restore Privacy")
        self.assertTrue(is_under_program_files(win, env))
        self.assertEqual(
            default_install_dir_for_platform("linux", {}),
            Path("/opt/restore-privacy"),
        )
        mac = default_install_dir_for_platform("darwin", {})
        # Path.as_posix() so Windows runners don't use backslash-only roots
        self.assertEqual(mac.as_posix(), "/Applications/Restore Privacy.app")


class TestBundleInventory(unittest.TestCase):
    def test_inventory_finds_client_and_restore_internet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "RestorePrivacy.exe").write_bytes(b"MZ")
            (root / "Restore Internet.bat").write_text("@echo off\n", encoding="utf-8")
            inv = inventory_install_bundle(root, platform="win32")
            self.assertTrue(inv.complete)
            self.assertEqual(inv.client_entry, "RestorePrivacy.exe")
            self.assertEqual(inv.restore_internet_entry, "Restore Internet.bat")
            self.assertIn("Restore Internet.bat", planned_windows_bundle_entries())

    def test_inventory_incomplete_without_restore_internet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "RestorePrivacy-0.4.5.exe").write_bytes(b"MZ")
            inv = inventory_install_bundle(root, platform="win32")
            self.assertIsNotNone(inv.client_entry)
            self.assertIsNone(inv.restore_internet_entry)
            self.assertFalse(inv.complete)

    def test_linux_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bin").mkdir()
            (root / "bin" / "privacy-restored").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "Restore Internet").write_text("#!/bin/sh\n", encoding="utf-8")
            inv = inventory_install_bundle(root, platform="linux")
            self.assertTrue(inv.complete)


class TestInstallerWiringStruct(unittest.TestCase):
    def test_installer_uses_install_paths_module(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("default_windows_install_dir", src)
        self.assertIn("install_paths", src)
        self.assertIn("Program Files", src)
        self.assertIn("Restore Internet", src)
        # Default INSTALL_DIR comes from Program Files helper (not LocalAppData only)
        self.assertIn("INSTALL_DIR = default_windows_install_dir()", src)
        self.assertIn("resolve_install_dir", src)

    def test_linux_package_ships_restore_internet(self):
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("Restore Internet", src)
        self.assertIn("write_restore_internet", src)
        self.assertIn("/opt/restore-privacy", src)


if __name__ == "__main__":
    unittest.main()
