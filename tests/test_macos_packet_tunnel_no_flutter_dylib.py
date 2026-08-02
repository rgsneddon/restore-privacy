"""PacketTunnel appex must not link Flutter plugin dylibs (dyld crash at startTunnel)."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBX = ROOT / "client_app/macos/Runner.xcodeproj/project.pbxproj"
PODFILE = ROOT / "client_app/macos/Podfile"
APPEX_BIN = (
    ROOT
    / "client_app/build/macos/Build/Products/Release/restore_privacy_client.app"
    / "Contents/PlugIns/PacketTunnel.appex/Contents/MacOS/PacketTunnel"
)


class TestPacketTunnelNoFlutterDylib(unittest.TestCase):
    def test_pbx_packet_tunnel_other_ldflags_exclude_flutter_plugins(self) -> None:
        text = PBX.read_text(encoding="utf-8")
        self.assertIn(
            "PRODUCT_BUNDLE_IDENTIFIER = com.restoreprivacy.restorePrivacyClient.PacketTunnel;",
            text,
        )
        self.assertIn("PacketTunnel must NOT inherit CocoaPods Flutter plugin", text)
        # Shipped target flags must not pull secure storage into the appex.
        self.assertNotIn("flutter_secure_storage", text)
        self.assertIn('"-framework",\n\t\t\t\t\tNetworkExtension,', text)

    def test_podfile_post_install_clears_packet_tunnel_plugin_ldflags(self) -> None:
        text = PODFILE.read_text(encoding="utf-8")
        self.assertIn("target.name == 'PacketTunnel'", text)
        self.assertIn("flutter_secure_storage_macos", text)

    def test_release_appex_otool_has_no_flutter_secure_if_built(self) -> None:
        if not APPEX_BIN.is_file():
            self.skipTest("Release PacketTunnel binary not built on this host")
        out = subprocess.check_output(["otool", "-L", str(APPEX_BIN)], text=True)
        self.assertNotIn("flutter_secure", out)
        self.assertIn("NetworkExtension", out)


if __name__ == "__main__":
    unittest.main()
