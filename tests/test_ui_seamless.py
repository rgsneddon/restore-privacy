"""Seamless product shell: Connect/status/Settings transparency + licence surface."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestWindowsSeamlessShell(unittest.TestCase):
    def test_primary_surface_controls(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_on_toggle_connect", src)
        self.assertIn("_start_connect", src)
        self.assertIn("_start_disconnect", src)
        self.assertIn("assert_may_connect", src)
        self.assertIn("_open_settings", src)
        self.assertIn("status_var", src)
        # Transparency still reachable
        self.assertIn("connection_log", src)
        self.assertIn("run_product_leak_test", src)
        self.assertIn("DPI_MITIGATION", src)
        # Licence surface
        self.assertIn("LICENCE_ACCEPT_BUTTON", src)
        self.assertIn("_show_licence_prompt", src)
        # Polish / seamless markers
        self.assertIn("SEAMLESS", src)
        self.assertIn("hero", src.lower())
        self.assertIn("status_card", src)


class TestFlutterSeamlessShell(unittest.TestCase):
    def test_primary_surface_controls(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        screen = (
            ROOT / "client_app" / "lib" / "settings_screen.dart"
        ).read_text(encoding="utf-8")
        reg = (
            ROOT / "client_app" / "lib" / "registration_copy.dart"
        ).read_text(encoding="utf-8")
        gate = (
            ROOT / "client_app" / "lib" / "licence_gate.dart"
        ).read_text(encoding="utf-8")
        self.assertIn("_onToggle", main)
        self.assertIn("Connect", main)
        self.assertIn("_openSettings", main)
        self.assertIn("assertMayConnect", main)
        self.assertIn("kLicenceAcceptButton", main + screen)
        self.assertIn("Accept licence", gate)
        self.assertIn("kConnectionLogTitle", screen)
        self.assertIn("kDpiMitigationDisclaimer", screen)
        self.assertIn("kLeakTestButton", screen)
        self.assertIn("kSeamless", main + reg)


if __name__ == "__main__":
    unittest.main()
