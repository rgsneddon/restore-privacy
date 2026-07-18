"""Full-tunnel honesty: Apple clients must not report Connected on host-only HELLO.

Residual public IP only changes when Packet Tunnel is active. The previous
false-positive path ran RptConnectOrchestrator, closed UDP, and returned ok:true
with a tunnel IP — UI said Connected while egress stayed on the ISP address.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"
CHANNELS = (
    APP / "ios" / "NativePrep" / "RptVpnChannel.swift",
    APP / "macos" / "NativePrep" / "RptVpnChannel.swift",
)
HONESTY_SWIFT = (
    APP / "apple_shared" / "Rpt2" / "Sources" / "Rpt2" / "RptFullTunnelResult.swift",
    APP / "ios" / "NativePrep" / "Rpt2" / "RptFullTunnelResult.swift",
    APP / "macos" / "NativePrep" / "Rpt2" / "RptFullTunnelResult.swift",
)
CONNECT_STATUS = APP / "lib" / "connect_status.dart"


class TestAppleChannelNoHostHelloSuccess(unittest.TestCase):
    def test_channels_exist(self):
        for p in CHANNELS:
            self.assertTrue(p.is_file(), f"missing {p}")

    def test_no_host_side_connect_success_fallback(self):
        """Old path: hostSideConnect → flutterResult(outcome.resultMap) with ok:true."""
        for p in CHANNELS:
            text = p.read_text(encoding="utf-8")
            self.assertNotIn(
                "hostSideConnect",
                text,
                f"{p.name} must not use hostSideConnect success fallback",
            )
            # Diagnostic path must close transport and never treat HELLO as product success.
            self.assertIn("hostSideDiagnostic", text)
            self.assertIn("closeTransport", text)
            self.assertIn("RptFullTunnelResult", text)
            self.assertIn("isProductSuccess", text)
            self.assertIn("packetTunnelActive", text)
            # Must not assign flutterResult from orchestrator resultMap directly.
            self.assertNotRegex(
                text,
                r"flutterResult\(\s*outcome\.resultMap\s*\)",
                msg=f"{p.name} must not return orchestrator resultMap as product success",
            )
            self.assertNotRegex(
                text,
                r"flutterResult\(\s*map\s*\)\s*\n\s*\}\s*\n\s*\}\s*\n\s*\}",
            )

    def test_full_tunnel_product_requires_ne_path(self):
        for p in CHANNELS:
            text = p.read_text(encoding="utf-8")
            self.assertIn("fullTunnel", text)
            self.assertIn("startTunnel", text)
            self.assertIn("pollTunnelConnected", text)
            self.assertIn("residual public ip", text.lower())
            # Product success only via RptFullTunnelResult with packetTunnelActive true path
            self.assertIn("productConnectMap", text)
            self.assertIn("hostOnlyHello", text)

    def test_honesty_helper_shipped_everywhere(self):
        for p in HONESTY_SWIFT:
            self.assertTrue(p.is_file(), f"missing honesty helper {p}")
            text = p.read_text(encoding="utf-8")
            self.assertIn("productConnectMap", text)
            self.assertIn("isProductSuccess", text)
            self.assertIn("packetTunnelNotActiveMessage", text)
            self.assertIn("hostOnlyHelloNotFullTunnelMessage", text)
            self.assertIn("residual public IP", text)
            # Host-only / NE-failure path hard-codes ok false (Swift spacing may vary)
            compact = re.sub(r"\s+", "", text)
            self.assertIn('"ok":false', compact)
            self.assertIn('"ok":true', compact)  # success branch still present for NE path
            # Success branch requires packetTunnelActive
            self.assertIn("packetTunnelActive", text)

    def test_dart_honesty_helpers(self):
        text = CONNECT_STATUS.read_text(encoding="utf-8")
        self.assertIn("buildFullTunnelConnectResult", text)
        self.assertIn("kPacketTunnelNotActiveMessage", text)
        self.assertIn("kHostOnlyHelloNotFullTunnelMessage", text)
        self.assertIn("hostOnlySession", text)
        self.assertIn("fullTunnelActive", text)
        # isConnectSuccess must reject host-only / inactive tunnel markers
        self.assertIn("hostOnlySession", text)
        self.assertRegex(
            text,
            r"if \(result\['hostOnlySession'\] == true\) return false;",
        )
        self.assertRegex(
            text,
            r"if \(result\['fullTunnelActive'\] == false\) return false;",
        )


class TestHonestyMessageContract(unittest.TestCase):
    """Representative maps — logic lives in Dart; assert shared message constants match Swift."""

    def test_swift_and_dart_residual_messages_align(self):
        dart = CONNECT_STATUS.read_text(encoding="utf-8")
        swift = HONESTY_SWIFT[0].read_text(encoding="utf-8")
        for needle in (
            "System VPN (Packet Tunnel) did not become active",
            "residual public IP",
            "Node session was assigned but the system Packet Tunnel is not carrying traffic",
        ):
            self.assertIn(needle, dart)
            self.assertIn(needle, swift)

    def test_pbxproj_compiles_honesty_helper(self):
        for rel in (
            "macos/Runner.xcodeproj/project.pbxproj",
            "ios/Runner.xcodeproj/project.pbxproj",
        ):
            pbx = (APP / rel).read_text(encoding="utf-8")
            self.assertIn("RptFullTunnelResult.swift", pbx)
            self.assertGreaterEqual(
                len(re.findall(r"RptFullTunnelResult\.swift in Sources", pbx)),
                1,
            )


if __name__ == "__main__":
    unittest.main()
