"""Structural gates: macOS residual Team sign path enables Packet Tunnel NE on host."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAC = ROOT / "client_app" / "macos"
TEAM_ENT = MAC / "Runner" / "TeamResidual.entitlements"
DEV_ID_ENT = MAC / "Runner" / "DeveloperID.entitlements"
APPEX_ENT = MAC / "PacketTunnel" / "PacketTunnel.entitlements"
SIGN_SCRIPT = ROOT / "scripts" / "sign_macos_residual_team.py"
CHANNEL = MAC / "NativePrep" / "RptVpnChannel.swift"


class TestMacosResidualTeamSign(unittest.TestCase):
    def test_team_residual_host_declares_ne(self):
        self.assertTrue(TEAM_ENT.is_file(), "TeamResidual.entitlements missing")
        text = TEAM_ENT.read_text(encoding="utf-8")
        self.assertIn("com.apple.developer.networking.networkextension", text)
        self.assertIn("packet-tunnel-provider", text)
        self.assertIn("com.apple.security.cs.allow-jit", text)
        # Forbidden combo that AMFI SIGKILLs with NE (even with profile)
        self.assertNotIn("allow-unsigned-executable-memory", text)
        self.assertNotIn("disable-library-validation", text)

    def test_developer_id_host_omits_ne(self):
        """Public DevID zip must keep opening without restricted host NE."""
        self.assertTrue(DEV_ID_ENT.is_file())
        stripped = re.sub(
            r"<!--.*?-->", "", DEV_ID_ENT.read_text(encoding="utf-8"), flags=re.S
        )
        self.assertNotIn("com.apple.developer.networking.networkextension", stripped)

    def test_appex_keeps_ne_and_app_group(self):
        text = APPEX_ENT.read_text(encoding="utf-8")
        self.assertIn("packet-tunnel-provider", text)
        self.assertIn("group.com.restoreprivacy.shared", text)

    def test_sign_script_embeds_profiles_and_team_identity(self):
        self.assertTrue(SIGN_SCRIPT.is_file())
        text = SIGN_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("TeamResidual.entitlements", text)
        self.assertIn("Apple Development", text)
        self.assertIn("embedded.provisionprofile", text)
        self.assertIn("com.restoreprivacy.restorePrivacyClient.PacketTunnel", text)
        self.assertIn("networkextension", text)

    def test_vpn_channel_selects_product_manager_and_surfaces_ne_errors(self):
        text = CHANNEL.read_text(encoding="utf-8")
        self.assertIn("providerBundleId", text)
        self.assertIn("com.restoreprivacy.restorePrivacyClient.PacketTunnel", text)
        self.assertIn("selectOrCreateManager", text)
        self.assertIn("describeNePreferencesError", text)
        self.assertIn("sign_macos_residual_team", text)
        self.assertIn("maxAttempts: 40", text)
        # Must not blindly use managers?.first for unrelated VPN configs
        self.assertIn("shouldStopManager", text)

    def test_honesty_message_mentions_team_residual_and_system_settings(self):
        dart = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("System VPN (Packet Tunnel) did not become active", dart)
        self.assertIn("sign_macos_residual_team", dart)
        self.assertIn("VPN & Filters", dart)
        swift = (
            ROOT
            / "client_app"
            / "apple_shared"
            / "Rpt2"
            / "Sources"
            / "Rpt2"
            / "RptFullTunnelResult.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("sign_macos_residual_team", swift)


if __name__ == "__main__":
    unittest.main()
