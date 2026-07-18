"""Structural checks: host + Packet Tunnel entitlement plists for real NE VPN.

Reads the shipped entitlement files and Xcode project wiring — residual public
IP only changes when these keys are present *and* Team-signed profiles exist.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"

HOST_ENTITLEMENTS = (
    APP / "macos" / "Runner" / "DebugProfile.entitlements",
    APP / "macos" / "Runner" / "Release.entitlements",
    APP / "ios" / "Runner" / "Runner.entitlements",
)
EXTENSION_ENTITLEMENTS = (
    APP / "macos" / "PacketTunnel" / "PacketTunnel.entitlements",
    APP / "ios" / "PacketTunnel" / "PacketTunnel.entitlements",
)

NE_KEY = "com.apple.developer.networking.networkextension"
PACKET_TUNNEL = "packet-tunnel-provider"
APP_GROUP_KEY = "com.apple.security.application-groups"
APP_GROUP = "group.com.restoreprivacy.shared"

HOST_BUNDLE = "com.restoreprivacy.restorePrivacyClient"
TUNNEL_BUNDLE = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"
TEAM = "SFCBP95595"


def _plist_text(path: Path) -> str:
    assert path.is_file(), f"missing entitlement file: {path}"
    return path.read_text(encoding="utf-8")


def _assert_ne_and_group(tc: unittest.TestCase, path: Path) -> None:
    text = _plist_text(path)
    tc.assertIn(NE_KEY, text, f"{path} missing NE key")
    tc.assertIn(PACKET_TUNNEL, text, f"{path} missing packet-tunnel-provider")
    tc.assertIn(APP_GROUP_KEY, text, f"{path} missing App Group key")
    tc.assertIn(APP_GROUP, text, f"{path} missing {APP_GROUP}")
    # Must not be only inside XML comments
    # Strip <!-- ... --> and re-check
    stripped = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    tc.assertIn(PACKET_TUNNEL, stripped, f"{path}: packet-tunnel-provider only in comment?")
    tc.assertIn(APP_GROUP, stripped, f"{path}: app group only in comment?")


class TestHostAndExtensionEntitlements(unittest.TestCase):
    def test_host_entitlements_declare_ne_and_app_group(self):
        for p in HOST_ENTITLEMENTS:
            with self.subTest(path=str(p.relative_to(ROOT))):
                _assert_ne_and_group(self, p)

    def test_extension_entitlements_declare_ne_and_app_group(self):
        for p in EXTENSION_ENTITLEMENTS:
            with self.subTest(path=str(p.relative_to(ROOT))):
                _assert_ne_and_group(self, p)

    def test_ios_host_entitlements_wired_in_pbxproj(self):
        pbx = (APP / "ios" / "Runner.xcodeproj" / "project.pbxproj").read_text(
            encoding="utf-8"
        )
        self.assertIn("CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;", pbx)
        self.assertGreaterEqual(
            pbx.count("CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;"),
            3,
            "Debug/Release/Profile should all wire host entitlements",
        )
        self.assertIn("Runner.entitlements", pbx)
        self.assertIn(f"DEVELOPMENT_TEAM = {TEAM};", pbx)

    def test_macos_host_entitlements_wired_in_pbxproj(self):
        pbx = (APP / "macos" / "Runner.xcodeproj" / "project.pbxproj").read_text(
            encoding="utf-8"
        )
        self.assertIn("CODE_SIGN_ENTITLEMENTS = Runner/DebugProfile.entitlements;", pbx)
        self.assertIn("CODE_SIGN_ENTITLEMENTS = Runner/Release.entitlements;", pbx)
        self.assertIn(
            "CODE_SIGN_ENTITLEMENTS = PacketTunnel/PacketTunnel.entitlements;", pbx
        )

    def test_bundle_ids_match_product(self):
        ios_pbx = (APP / "ios" / "Runner.xcodeproj" / "project.pbxproj").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {HOST_BUNDLE};", ios_pbx)
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {TUNNEL_BUNDLE};", ios_pbx)

        # macOS host PRODUCT_BUNDLE_IDENTIFIER lives in AppInfo.xcconfig
        mac_appinfo = (
            APP / "macos" / "Runner" / "Configs" / "AppInfo.xcconfig"
        ).read_text(encoding="utf-8")
        self.assertIn(HOST_BUNDLE, mac_appinfo)
        mac_pbx = (APP / "macos" / "Runner.xcodeproj" / "project.pbxproj").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {TUNNEL_BUNDLE};", mac_pbx)

    def test_channel_provider_bundle_matches_tunnel(self):
        for rel in (
            "ios/NativePrep/RptVpnChannel.swift",
            "macos/NativePrep/RptVpnChannel.swift",
        ):
            text = (APP / rel).read_text(encoding="utf-8")
            self.assertIn(f'providerBundleId = "{TUNNEL_BUNDLE}"', text)

    def test_packet_tunnel_team_signing_enabled(self):
        """PacketTunnel must Team-sign so the OS can load the NE (not ad-hoc only)."""
        for rel in (
            "ios/Runner.xcodeproj/project.pbxproj",
            "macos/Runner.xcodeproj/project.pbxproj",
        ):
            pbx = (APP / rel).read_text(encoding="utf-8")
            # PacketTunnel configs: ALLOWED/REQUIRED YES with product bundle
            self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {TUNNEL_BUNDLE};", pbx)
            self.assertIn("CODE_SIGNING_ALLOWED = YES;", pbx)
            self.assertIn("CODE_SIGNING_REQUIRED = YES;", pbx)
            # Ad-hoc re-sign must not run when Team signing is on
            self.assertIn("skip ad-hoc re-sign", pbx)
            self.assertIn("CODE_SIGNING_ALLOWED", pbx)

    def test_packet_tunnel_info_plist_extension_point(self):
        for rel in (
            "ios/PacketTunnel/Info.plist",
            "macos/PacketTunnel/Info.plist",
        ):
            text = (APP / rel).read_text(encoding="utf-8")
            self.assertIn("com.apple.networkextension.packet-tunnel", text)
            self.assertIn("PacketTunnelProvider", text)
            self.assertIn("NEProviderClasses", text)


class TestOperatorChecklistDocs(unittest.TestCase):
    def test_apple_build_operator_checklist(self):
        text = (APP / "APPLE_BUILD.md").read_text(encoding="utf-8")
        self.assertIn("Operator checklist", text)
        self.assertIn(HOST_BUNDLE, text)
        self.assertIn(TUNNEL_BUNDLE, text)
        self.assertIn(APP_GROUP, text)
        self.assertIn(TEAM, text)
        self.assertIn("CODE_SIGNING_ALLOWED", text)
        self.assertIn("packet-tunnel-provider", text)
        self.assertIn("residual", text.lower())
        # Ordered steps markers
        for needle in (
            "Developer portal",
            "Xcode",
            "PacketTunnel target",
            "Secrets",
            "Build and run",
            "Confirm residual public IP",
        ):
            self.assertIn(needle, text)

    def test_platform_docs_point_at_checklist(self):
        for rel in ("ios/BUILD_ON_MAC.md", "macos/BUILD_ON_MAC.md"):
            text = (APP / rel).read_text(encoding="utf-8")
            self.assertIn(HOST_BUNDLE, text)
            self.assertIn(TUNNEL_BUNDLE, text)
            self.assertIn(APP_GROUP, text)
            self.assertIn("Operator checklist", text)
            self.assertIn("APPLE_BUILD.md", text)


if __name__ == "__main__":
    unittest.main()
