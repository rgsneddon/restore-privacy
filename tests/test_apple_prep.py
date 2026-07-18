"""Structural prep checks for iOS/macOS MacBook builds (no Xcode on Windows)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"


class TestApplePrepDocs(unittest.TestCase):
    def test_master_apple_build_doc(self):
        p = APP / "APPLE_BUILD.md"
        self.assertTrue(p.is_file(), "missing APPLE_BUILD.md")
        text = p.read_text(encoding="utf-8")
        self.assertIn("Network Extension", text)
        self.assertIn("Packet Tunnel", text)
        self.assertIn("client_ed25519.priv", text)
        self.assertIn("node_elgamal.pub", text)
        self.assertIn("node_elgamal.priv", text)  # must say never ship
        self.assertIn("restore_privacy/vpn", text)
        self.assertIn("signing", text.lower() or "Signing" in text)
        self.assertIn("flutter build ios", text)
        self.assertIn("flutter build macos", text)

    def test_ios_build_on_mac(self):
        p = APP / "ios" / "BUILD_ON_MAC.md"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("Packet Tunnel", text)
        self.assertIn("NEPacketTunnelProvider", text)
        self.assertIn("restore_privacy/vpn", text)
        self.assertIn("client_ed25519.priv", text)
        self.assertIn("Signing", text)
        self.assertIn("open ios/Runner.xcworkspace", text)

    def test_macos_build_on_mac(self):
        p = APP / "macos" / "BUILD_ON_MAC.md"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("Network Extension", text)
        self.assertIn("Packet Tunnel", text)
        self.assertIn("restore_privacy/vpn", text)
        self.assertIn("notar", text.lower())
        self.assertIn("flutter build macos", text)
        self.assertIn("client_ed25519.priv", text)


class TestAppleNativePrepStubs(unittest.TestCase):
    def test_ios_native_prep_files(self):
        base = APP / "ios" / "NativePrep"
        for name in (
            "RptVpnChannel.swift",
            "PacketTunnelProvider.swift",
            "RptSecrets.swift",
            "RPT_PROTOCOL.md",
            "Runner.entitlements.example",
        ):
            p = base / name
            self.assertTrue(p.is_file(), f"missing {p}")
            self.assertGreater(p.stat().st_size, 50)

    def test_macos_native_prep_files(self):
        base = APP / "macos" / "NativePrep"
        for name in (
            "RptVpnChannel.swift",
            "PacketTunnelProvider.swift",
            "RptSecrets.swift",
            "Runner.entitlements.example",
        ):
            p = base / name
            self.assertTrue(p.is_file(), f"missing {p}")
            self.assertGreater(p.stat().st_size, 50)

    def test_channel_name_matches_flutter(self):
        dart = (APP / "lib" / "vpn_controller.dart").read_text(encoding="utf-8")
        self.assertIn("restore_privacy/vpn", dart)
        ios = (APP / "ios" / "NativePrep" / "RptVpnChannel.swift").read_text(
            encoding="utf-8"
        )
        mac = (APP / "macos" / "NativePrep" / "RptVpnChannel.swift").read_text(
            encoding="utf-8"
        )
        self.assertIn('static let name = "restore_privacy/vpn"', ios)
        self.assertIn("restore_privacy/vpn", ios)
        self.assertIn("restore_privacy/vpn", mac)
        self.assertIn("connect", ios)
        self.assertIn("disconnect", ios)

    def test_protocol_doc_references_python(self):
        text = (APP / "ios" / "NativePrep" / "RPT_PROTOCOL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("RPT2", text)
        self.assertIn("client/connect.py", text)
        self.assertIn("node/handshake.py", text)
        self.assertIn("client/dataplane.py", text)
        self.assertIn("KEEPALIVE", text)

    def test_secrets_helpers_forbid_node_priv(self):
        for rel in (
            "ios/NativePrep/RptSecrets.swift",
            "macos/NativePrep/RptSecrets.swift",
        ):
            t = (APP / rel).read_text(encoding="utf-8")
            self.assertIn("client_ed25519.priv", t)
            self.assertIn("node_elgamal.pub", t)
            self.assertIn("node_elgamal.priv", t)
            self.assertTrue(
                "never" in t.lower(),
                f"must warn never ship node priv: {rel}",
            )


class TestAppleProjectTrees(unittest.TestCase):
    def test_ios_xcode_tree(self):
        self.assertTrue((APP / "ios" / "Runner.xcworkspace").is_dir())
        self.assertTrue((APP / "ios" / "Runner.xcodeproj" / "project.pbxproj").is_file())
        self.assertTrue((APP / "ios" / "Runner" / "AppDelegate.swift").is_file())
        self.assertTrue((APP / "ios" / "Runner" / "Info.plist").is_file())

    def test_macos_xcode_tree(self):
        self.assertTrue((APP / "macos" / "Runner.xcworkspace").is_dir())
        self.assertTrue(
            (APP / "macos" / "Runner.xcodeproj" / "project.pbxproj").is_file()
        )
        self.assertTrue((APP / "macos" / "Runner" / "AppDelegate.swift").is_file())
        self.assertTrue(
            (APP / "macos" / "Runner" / "DebugProfile.entitlements").is_file()
        )
        self.assertTrue((APP / "macos" / "Runner" / "Release.entitlements").is_file())

    def test_app_icons_present(self):
        ios_icon = (
            APP
            / "ios"
            / "Runner"
            / "Assets.xcassets"
            / "AppIcon.appiconset"
            / "Icon-App-1024x1024@1x.png"
        )
        mac_icon = (
            APP
            / "macos"
            / "Runner"
            / "Assets.xcassets"
            / "AppIcon.appiconset"
            / "app_icon_1024.png"
        )
        self.assertTrue(ios_icon.is_file())
        self.assertGreater(ios_icon.stat().st_size, 5_000)
        self.assertTrue(mac_icon.is_file())
        self.assertGreater(mac_icon.stat().st_size, 5_000)

    def test_shared_rpt_config(self):
        cfg = (APP / "lib" / "rpt_config.dart").read_text(encoding="utf-8")
        self.assertIn("104.156.224.47", cfg)
        self.assertIn("44044", cfg)
        self.assertIn("fullTunnel = true", cfg)
        self.assertIn("autoConnectOnLaunch = true", cfg)
        self.assertIn("RPT2", cfg)


class TestNoPrivInApplePrep(unittest.TestCase):
    def test_no_priv_files_under_native_prep(self):
        for base in (APP / "ios" / "NativePrep", APP / "macos" / "NativePrep"):
            for p in base.rglob("*"):
                if p.is_file():
                    self.assertFalse(
                        p.name.endswith(".priv"),
                        f"must not ship priv in prep: {p}",
                    )

    def test_no_priv_under_ios_macos_source_trees(self):
        for sub in ("ios", "macos"):
            for p in (APP / sub).rglob("*.priv"):
                # Ignore anything under build/ intermediates if present
                if "build" in p.parts:
                    continue
                self.fail(f"must not place *.priv in Apple tree: {p}")


if __name__ == "__main__":
    unittest.main()
