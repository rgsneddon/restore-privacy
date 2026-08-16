"""Catalog macOS zip must install to Applications — not launch from the zip."""

from __future__ import annotations

import importlib.util
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PKG = SCRIPTS / "macos_catalog_zip.py"


def _load():
    spec = importlib.util.spec_from_file_location("macos_catalog_zip", PKG)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class MacosCatalogZipInstallWrapper(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not PKG.is_file():
            raise unittest.SkipTest("macos_catalog_zip.py missing")
        cls.pkg = _load()

    def test_install_copy_forbids_in_zip_open(self) -> None:
        how = self.pkg.how_to_install_text().lower()
        self.assertIn("applications", how)
        self.assertIn("do not open the app from inside the zip", how)
        cmd = self.pkg.install_command_text()
        self.assertIn("/Applications/restore_privacy_client.app", cmd)
        self.assertIn("ditto", cmd)
        self.assertIn("open", cmd)

    def test_package_zip_contains_app_and_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rpt_macos_wrap_") as td:
            root = Path(td)
            app = root / "restore_privacy_client.app"
            macos = app / "Contents" / "MacOS"
            macos.mkdir(parents=True)
            (app / "Contents" / "Info.plist").write_text(
                '<?xml version="1.0"?><plist><dict></dict></plist>\n',
                encoding="utf-8",
            )
            (macos / "restore_privacy_client").write_bytes(b"\0")
            dest = root / "restore-privacy-client-1.2.7-macos.zip"
            self.pkg.package_macos_catalog_zip(app, dest)
            self.assertTrue(dest.is_file())
            self.assertTrue(self.pkg.zip_has_install_wrapper(dest))
            with zipfile.ZipFile(dest) as zf:
                names = zf.namelist()
            self.assertTrue(
                any(
                    n.endswith("restore_privacy_client.app/Contents/Info.plist")
                    for n in names
                )
            )
            self.assertTrue(
                any(n.endswith("Install Restore Privacy.command") for n in names)
            )
            self.assertTrue(any(n.endswith("How to Install.txt") for n in names))
            self.assertTrue(any(n.rstrip("/").endswith("Applications") for n in names))

            with zipfile.ZipFile(dest) as zf:
                cmds = [
                    i
                    for i in zf.infolist()
                    if i.filename.endswith("Install Restore Privacy.command")
                ]
            self.assertTrue(cmds)
            unix_mode = cmds[0].external_attr >> 16
            self.assertTrue(unix_mode & stat.S_IXUSR, oct(unix_mode))

    def test_build_suite_and_sign_use_wrapper(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        suite = (SCRIPTS / f"build_suite_{pin}.py").read_text(encoding="utf-8")
        sign = (SCRIPTS / "sign_and_notarize_macos.py").read_text(encoding="utf-8")
        self.assertIn("package_macos_catalog_zip", suite)
        self.assertIn("package_macos_catalog_zip", sign)


if __name__ == "__main__":
    unittest.main()
