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

    def test_flutter_does_not_auto_hide_on_connect_success(self):
        """Connect success keeps window open; tray may still update."""
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        self.assertIn("macos_window.dart", main)
        self.assertIn("shouldHideToTrayAfterConnectSuccess", main)
        self.assertIn("MacWindowController", main)
        self.assertIn("onTrayDisconnect", main)
        self.assertIn("setTrayConnected", main)
        # Product path still gates hide behind the policy helper (now always false).
        self.assertIn("shouldHideToTrayAfterConnectSuccess(ok)", main)

    def test_pure_hide_gate_keeps_window_open(self):
        cs = (LIB / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("shouldHideToTrayAfterConnect", cs)
        self.assertIn("shouldHideToTrayAfterConnectSuccess", cs)
        # Policy: return false (stay open) — not hide on isConnectSuccess.
        self.assertIn("return false", cs)
        # Must not re-enable hide-on-success via isConnectSuccess alone
        hide_fn = cs.split("bool shouldHideToTrayAfterConnect(")[1].split(
            "bool shouldHideToTrayAfterConnectSuccess"
        )[0]
        self.assertNotIn("isConnectSuccess(result)", hide_fn)

    def test_keygen_sheet_dismisses_on_valid_unlock(self):
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        cs = (LIB / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("shouldDismissKeygenSheetAfterUnlock", cs)
        self.assertIn("shouldDismissKeygenSheetAfterUnlock", main)
        self.assertIn("Navigator.of(ctx).pop()", main)
        # Success path: dismiss helper before pop
        kg = main.split("importKeygenAndVerify")[1].split("FilledButton")[0]
        self.assertIn("shouldDismissKeygenSheetAfterUnlock", kg)
        # pop only after valid unlock branch (paymentAllowsConnect path)
        self.assertIn("paymentAllowsConnect", main)

    def test_macos_window_channel_name(self):
        mw = (LIB / "macos_window.dart").read_text(encoding="utf-8")
        self.assertIn("restore_privacy/window", mw)
        self.assertIn("hideToTray", mw)
        self.assertIn("showFromTray", mw)
        self.assertIn("trayDisconnect", mw)
        self.assertIn("setTrayConnected", mw)


if __name__ == "__main__":
    unittest.main()
