"""Installer must ship full Restore Internet failsafe (not rmdir-only stub)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.installer import (  # noqa: E402
    FULL_RESTORE_INTERNET_BAT_EMBEDDED,
    is_full_restore_internet_failsafe,
    load_full_restore_internet_bat_text,
    ship_restore_internet_failsafe,
)


class TestFullRestoreInternetFailsafe(unittest.TestCase):
    def test_source_bat_is_full_failsafe(self):
        src = ROOT / "client" / "windows" / "Restore Internet.bat"
        self.assertTrue(src.is_file(), f"missing {src}")
        text = src.read_text(encoding="utf-8", errors="replace")
        self.assertTrue(is_full_restore_internet_failsafe(text), text[:200])
        low = text.lower()
        self.assertIn("0.0.0.0", text)
        self.assertIn("128.0.0.0", text)
        self.assertIn("rpt-ks", low)
        self.assertIn("remove-netfirewallrule", low.replace(" ", ""))
        # Product removal
        self.assertIn("restoreprivacy", low)

    def test_embedded_fallback_is_full_not_stub(self):
        body = FULL_RESTORE_INTERNET_BAT_EMBEDDED
        self.assertTrue(is_full_restore_internet_failsafe(body))
        # Reject classic three-line stub shape
        stub = (
            "@echo off\r\n"
            "route delete 0.0.0.0 mask 128.0.0.0\r\n"
            "route delete 128.0.0.0 mask 128.0.0.0\r\n"
            "route delete 82.221.101.241 mask 255.255.255.255\r\n"
            'rmdir /s /q "C:\\Users\\x\\AppData\\Local\\Programs\\RestorePrivacy"\r\n'
        )
        self.assertFalse(is_full_restore_internet_failsafe(stub))

    def test_load_prefers_full_body(self):
        text = load_full_restore_internet_bat_text()
        self.assertTrue(is_full_restore_internet_failsafe(text))
        self.assertIn("RPT-KS", text)
        self.assertIn("DefaultOutboundAction", text)

    def test_ship_writes_full_bat_and_alias(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            primary = ship_restore_internet_failsafe(root)
            self.assertEqual(primary.name, "Restore Internet.bat")
            self.assertTrue(primary.is_file())
            alias = root / "RestoreInternet.bat"
            self.assertTrue(alias.is_file())
            body = primary.read_text(encoding="utf-8")
            self.assertTrue(is_full_restore_internet_failsafe(body))
            # Uninstall.bat pattern: call Restore Internet
            uninst = (
                "@echo off\r\n"
                'if exist "%~dp0Restore Internet.bat" (\r\n'
                '  call "%~dp0Restore Internet.bat" %*\r\n'
                "  exit /b %ERRORLEVEL%\r\n"
                ")\r\n"
            )
            (root / "Uninstall.bat").write_text(uninst, encoding="utf-8")
            u = (root / "Uninstall.bat").read_text(encoding="utf-8")
            self.assertIn("Restore Internet.bat", u)

    def test_installer_module_calls_ship_not_stub_write(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ship_restore_internet_failsafe", src)
        self.assertIn("is_full_restore_internet_failsafe", src)
        # Historical stub fragment must not be the only fallback path
        self.assertIn("FULL_RESTORE_INTERNET_BAT_EMBEDDED", src)
        # Uninstall still aliases Restore Internet
        self.assertIn("Uninstall.bat", src)
        self.assertIn("Restore Internet.bat", src)


if __name__ == "__main__":
    unittest.main()
