"""Apple residual installs IPv6 ISP leak mitigation while Packet Tunnel is up."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestIpv6ResidualProtection(unittest.TestCase):
    def test_packet_tunnel_installs_ipv6_mitigation(self):
        for rel in (
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("ipv6IspLeakMitigationSettings", text, rel)
            self.assertIn("NEIPv6Route.default()", text, rel)
            self.assertIn("settings.ipv6Settings = Self.ipv6IspLeakMitigationSettings()", text, rel)
            self.assertNotIn("settings.ipv6Settings = nil", text, rel)
            self.assertIn('"ipv6Protected": true', text, rel)

    def test_product_connect_map_defaults_ipv6_protected(self):
        text = (
            ROOT
            / "client_app"
            / "apple_shared"
            / "Rpt2"
            / "Sources"
            / "Rpt2"
            / "RptFullTunnelResult.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("ipv6Protected: Bool = true", text)
        self.assertIn("ipv6IspPathBlockedMessage", text)
        self.assertIn("IPv6 ISP path blocked", text)

    def test_dart_build_result_defaults_protected(self):
        text = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("bool ipv6Protected = true", text)
        self.assertIn("IPv6 ISP path blocked", text)


if __name__ == "__main__":
    unittest.main()
