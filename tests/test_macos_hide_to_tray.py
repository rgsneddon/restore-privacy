"""Structural gates: macOS hide-to-tray after product full-tunnel Connect."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAC = ROOT / "client_app" / "macos"
LIB = ROOT / "client_app" / "lib"


class TestMacosHideToTrayWiring(unittest.TestCase):
    def test_tray_controller_swift_exists_and_registers_channel(self):
        p = MAC / "Runner" / "RptTrayController.swift"
        self.assertTrue(p.is_file(), "RptTrayController.swift missing")
        text = p.read_text(encoding="utf-8")
        self.assertIn("restore_privacy/window", text)
        self.assertIn("hideToTray", text)
        self.assertIn("showFromTray", text)
        self.assertIn("NSStatusItem", text)
        self.assertIn("shouldTerminateAfterLastWindowClosed", text)
        self.assertIn("trayDisconnect", text)
        # Must not stop Packet Tunnel on hide
        self.assertNotIn("stopVPNTunnel", text)
        self.assertNotIn("stopAllTunnels", text)

    def test_app_delegate_defers_quit_to_tray_mode(self):
        text = (MAC / "Runner" / "AppDelegate.swift").read_text(encoding="utf-8")
        self.assertIn("RptTrayController.shouldTerminateAfterLastWindowClosed", text)

    def test_main_flutter_window_registers_tray_and_hides_on_close(self):
        text = (MAC / "Runner" / "MainFlutterWindow.swift").read_text(encoding="utf-8")
        self.assertIn("RptTrayController.register", text)
        self.assertIn("orderOut", text)

    def test_pbxproj_compiles_tray_controller(self):
        pbx = (MAC / "Runner.xcodeproj" / "project.pbxproj").read_text(encoding="utf-8")
        self.assertIn("RptTrayController.swift", pbx)
        self.assertIn("RptTrayController.swift in Sources", pbx)

    def test_flutter_wires_hide_after_product_success(self):
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        self.assertIn("macos_window.dart", main)
        self.assertIn("shouldHideToTrayAfterConnectSuccess", main)
        self.assertIn("hideToTray", main)
        self.assertIn("MacWindowController", main)
        # main.dart wires the callback name; the channel method string lives in
        # macos_window.dart / RptTrayController.swift (see tests below).
        self.assertIn("onTrayDisconnect", main)
        self.assertIn("setTrayConnected", main)

    def test_pure_hide_gate_in_connect_status(self):
        cs = (LIB / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("shouldHideToTrayAfterConnect", cs)
        self.assertIn("shouldHideToTrayAfterConnectSuccess", cs)
        # Gate must call isConnectSuccess semantics
        self.assertIn("isConnectSuccess(result)", cs)

    def test_macos_window_channel_name(self):
        mw = (LIB / "macos_window.dart").read_text(encoding="utf-8")
        self.assertIn("restore_privacy/window", mw)
        self.assertIn("hideToTray", mw)
        self.assertIn("showFromTray", mw)
        self.assertIn("trayDisconnect", mw)
        self.assertIn("setTrayConnected", mw)


if __name__ == "__main__":
    unittest.main()
