"""Connect must not auto-open Network Settings except on permission denial."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWIFT = ROOT / "client_app" / "macos" / "NativePrep" / "RptVpnChannel.swift"
DART = ROOT / "client_app" / "lib" / "connect_status.dart"
VPN = ROOT / "client_app" / "lib" / "vpn_controller.dart"


class TestConnectSettingsAutoOpen(unittest.TestCase):
    def test_dart_auto_open_is_strict_permission_only(self):
        dart = DART.read_text(encoding="utf-8")
        self.assertIn("shouldAutoOpenVpnSystemSettings", dart)
        self.assertIn("isStrictVpnPermissionDenialMessage", dart)
        self.assertIn("needsTeamResidualSign", dart)
        # hostOnlySession alone must not auto-open
        auto = dart[dart.index("shouldAutoOpenVpnSystemSettings") :]
        auto = auto[: auto.index("\nbool shouldShowOpenVpnSettingsControl")]
        self.assertNotIn("hostOnlySession", auto)

    def test_flutter_connect_uses_auto_open_helper(self):
        vpn = VPN.read_text(encoding="utf-8")
        self.assertIn("shouldAutoOpenVpnSystemSettings", vpn)
        # connect path must not use broad shouldPrompt alone without auto helper
        conn = vpn[vpn.index("Future<bool> connect()") :]
        conn = conn[: conn.index("Future<bool> openVpnSystemSettings")]
        self.assertIn("shouldAutoOpenVpnSystemSettings", conn)

    def test_macos_connect_failure_gates_settings_open(self):
        text = SWIFT.read_text(encoding="utf-8")
        self.assertIn("permissionClass", text)
        # tunnel start failure must not always openSettings: true
        after = text.split("Packet Tunnel did not become Connected", 1)[1][:500]
        self.assertNotIn("openSettings: true", after)
        # host-only HELLO alone must not force open
        diag = text[text.index("hostSideDiagnostic") :]
        # shouldOpen requires openVpnSettings AND permission detail
        compact = "".join(text.split())
        self.assertIn(
            "openVpnSettings&&isNePermissionFailureDetail(detail)",
            compact,
        )


if __name__ == "__main__":
    unittest.main()
