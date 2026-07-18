"""App quit must stop Packet Tunnel so residual public IP returns (iOS + macOS)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"


class TestAppleQuitStopsTunnel(unittest.TestCase):
    def test_macos_app_delegate_stops_on_terminate(self):
        text = (APP / "macos" / "Runner" / "AppDelegate.swift").read_text(encoding="utf-8")
        self.assertIn("applicationShouldTerminate", text)
        self.assertIn("applicationWillTerminate", text)
        self.assertIn("stopAllTunnels", text)
        self.assertIn("stopAllTunnelsAndWait", text)
        self.assertIn("terminateLater", text)
        self.assertIn("RptVpnChannel", text)

    def test_ios_app_delegate_stops_on_will_terminate_and_background(self):
        text = (APP / "ios" / "Runner" / "AppDelegate.swift").read_text(encoding="utf-8")
        self.assertIn("applicationWillTerminate", text)
        # Blocking wait — stopVPNTunnel issued before process exit races loadAllFromPreferences
        self.assertIn("stopAllTunnelsAndWait", text)
        # App-switcher swipe-kill rarely gets willTerminate; background stop covers it
        self.assertIn("applicationDidEnterBackground", text)
        self.assertIn("stopAllTunnels", text)
        self.assertIn("RptVpnChannel", text)

    def test_ios_scene_delegate_stops_on_background(self):
        text = (APP / "ios" / "Runner" / "SceneDelegate.swift").read_text(encoding="utf-8")
        self.assertIn("sceneDidEnterBackground", text)
        self.assertIn("stopAllTunnels", text)

    def test_channel_disconnect_uses_stop_all_tunnels(self):
        for rel in (
            "ios/NativePrep/RptVpnChannel.swift",
            "macos/NativePrep/RptVpnChannel.swift",
        ):
            text = (APP / rel).read_text(encoding="utf-8")
            self.assertIn("stopAllTunnels", text)
            self.assertIn("stopAllTunnelsAndWait", text)
            self.assertIn("DispatchSemaphore", text)
            self.assertIn("stopVPNTunnel", text)
            self.assertIn('case "disconnect"', text)
            # disconnect case must call stopAllTunnels (not a parallel private disconnect)
            self.assertIn("stopAllTunnels { map in result(map) }", text)
            self.assertIn("disconnectResultMap", text)
            self.assertIn("fullTunnelActive", text)

    def test_packet_tunnel_provider_stop_closes_transport(self):
        for rel in (
            "ios/NativePrep/PacketTunnelProvider.swift",
            "macos/NativePrep/PacketTunnelProvider.swift",
        ):
            text = (APP / rel).read_text(encoding="utf-8")
            self.assertIn("func stopTunnel", text)
            self.assertIn("closeTransport", text)

    def test_flutter_lifecycle_wires_disconnect(self):
        main = (APP / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("WidgetsBindingObserver", main)
        self.assertIn("didChangeAppLifecycleState", main)
        self.assertIn("shouldStopTunnelOnAppLifecycle", main)
        self.assertIn("_vpn.disconnect()", main)
        # dispose also disconnects
        self.assertIn("void dispose()", main)

    def test_dart_stop_on_lifecycle_helper(self):
        text = (APP / "lib" / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("shouldStopTunnelOnAppLifecycle", text)
        self.assertIn("kDisconnectedResidualIpMessage", text)
        self.assertIn("detached", text)
        self.assertIn("paused", text)  # iOS app-switcher close
        # residual-IP reversion is documented next to the helper
        self.assertIn("residual public ip", text.lower())

    def test_disconnect_result_not_product_success_in_swift_helper(self):
        for rel in (
            "apple_shared/Rpt2/Sources/Rpt2/RptFullTunnelResult.swift",
            "ios/NativePrep/Rpt2/RptFullTunnelResult.swift",
            "macos/NativePrep/Rpt2/RptFullTunnelResult.swift",
        ):
            text = (APP / rel).read_text(encoding="utf-8")
            self.assertIn("disconnectResultMap", text)
            self.assertIn("fullTunnelActive", text)
            self.assertIn("residual public IP", text)


if __name__ == "__main__":
    unittest.main()
