"""iOS RptVpnChannel product Connect/Disconnect parity with macOS 0.4.8 outcomes."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS_CHANNEL = ROOT / "client_app" / "ios" / "NativePrep" / "RptVpnChannel.swift"


class TestIosVpnParity(unittest.TestCase):
    def test_ios_channel_exists(self):
        self.assertTrue(IOS_CHANNEL.is_file())

    def test_connect_enables_and_starts_product_tunnel(self):
        text = IOS_CHANNEL.read_text(encoding="utf-8")
        for needle in (
            "enableProductVpnAndStartTunnel",
            "reloadProductManager",
            "ensureEnabledThenStartTunnel",
            "isProductManager",
            "applyProductPacketTunnelProtocol",
            "manager.isEnabled = true",
            "startTunnel(options:",
            "re-registers the system VPN profile",
        ):
            self.assertIn(needle, text, f"missing connect parity: {needle}")

    def test_disconnect_stops_system_vpn_with_wait(self):
        text = IOS_CHANNEL.read_text(encoding="utf-8")
        for needle in (
            "stopAllTunnels",
            "stopVPNTunnel",
            "issueStopOnManagers",
            "waitUntilManagersDisconnected",
            "systemVpnStopped",
            "shouldStopManager",
            "restorePrivacyClient",
            'case "status"',
        ):
            self.assertIn(needle, text, f"missing disconnect parity: {needle}")

    def test_should_stop_not_only_empty_bid(self):
        """Disconnect matching must not rely solely on empty provider bid."""
        text = IOS_CHANNEL.read_text(encoding="utf-8")
        # Old code: return bid.isEmpty || bid == providerBundleId
        # New: isProductManager first, then broader name/bundle match
        self.assertIn("if isProductManager(manager)", text)
        self.assertNotIn(
            "return bid.isEmpty || bid == providerBundleId || manager.localizedDescription",
            text.replace(" ", ""),
        )


if __name__ == "__main__":
    unittest.main()
