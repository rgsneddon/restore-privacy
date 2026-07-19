"""Apple: explicit Disconnect stops tunnel; macOS quit must NOT auto-stop (product policy)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"


class TestAppleDisconnectAndQuitPolicy(unittest.TestCase):
    def test_macos_app_delegate_does_not_stop_on_quit(self):
        """Closing/quitting the Mac host leaves the tunnel up until Disconnect."""
        text = (APP / "macos" / "Runner" / "AppDelegate.swift").read_text(encoding="utf-8")
        self.assertNotIn("stopAllTunnels", text)
        self.assertNotIn("stopAllTunnelsAndWait", text)
        # applicationShouldTerminateAfterLastWindowClosed is OK; do not hook quit-stop
        self.assertNotIn("func applicationShouldTerminate(", text)
        self.assertNotIn("applicationWillTerminate", text)
        self.assertNotIn("terminateLater", text)
        self.assertNotIn("reply(toApplicationShouldTerminate", text)
        self.assertIn("FlutterAppDelegate", text)

    def test_channel_disconnect_uses_stop_all_tunnels(self):
        """Explicit method-channel disconnect still fully stops Packet Tunnel."""
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

    def test_flutter_explicit_disconnect_button(self):
        """Product: Disconnect button only — not lifecycle/dispose auto-stop."""
        main = (APP / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("_vpn.disconnect()", main)
        self.assertIn("_onToggle", main)
        self.assertIn("void dispose()", main)
        disp = main[main.index("void dispose") : main.index("void dispose") + 200]
        self.assertNotIn("_vpn.disconnect", disp)

    def test_dart_lifecycle_helper_never_auto_stops(self):
        text = (APP / "lib" / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("shouldStopTunnelOnAppLifecycle", text)
        self.assertIn("kDisconnectedResidualIpMessage", text)
        self.assertIn("return false", text)

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
