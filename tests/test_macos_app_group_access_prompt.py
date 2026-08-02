"""Structural proof: macOS “access data from other apps” is App Group host↔PacketTunnel.

Drives real shipped entitlement plists + Swift sources (not a re-implemented story).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACOS = ROOT / "client_app" / "macos"
GROUP_ID = "group.com.restoreprivacy.shared"

HOST_ENTITLEMENTS = [
    MACOS / "Runner" / "DeveloperID.entitlements",
    MACOS / "Runner" / "Release.entitlements",
    MACOS / "Runner" / "DebugProfile.entitlements",
]
APPEX_ENTITLEMENTS = MACOS / "PacketTunnel" / "PacketTunnel.entitlements"
SECRETS = MACOS / "NativePrep" / "RptSecrets.swift"
VPN_CHANNEL = MACOS / "NativePrep" / "RptVpnChannel.swift"
DOC = ROOT / "client_app" / "APPLE_APP_GROUP_ACCESS.md"


class TestMacosAppGroupAccessPrompt(unittest.TestCase):
    def test_host_and_appex_declare_same_app_group(self) -> None:
        for path in HOST_ENTITLEMENTS:
            self.assertTrue(path.is_file(), f"missing {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn("com.apple.security.application-groups", text)
            self.assertIn(GROUP_ID, text)
        self.assertTrue(APPEX_ENTITLEMENTS.is_file())
        appex = APPEX_ENTITLEMENTS.read_text(encoding="utf-8")
        self.assertIn("com.apple.security.application-groups", appex)
        self.assertIn(GROUP_ID, appex)
        self.assertIn("packet-tunnel-provider", appex)

    def test_rpt_secrets_app_group_id_and_container_api(self) -> None:
        src = SECRETS.read_text(encoding="utf-8")
        # Shipped constant — product peer container id.
        self.assertRegex(
            src,
            r'appGroupId:\s*String\s*\{\s*"group\.com\.restoreprivacy\.shared"\s*\}',
        )
        self.assertIn(
            "containerURL(forSecurityApplicationGroupIdentifier:",
            src,
        )
        self.assertIn("seedAppGroupFromKnownSourcesIfNeeded", src)

    def test_channel_register_seeds_app_group_on_startup(self) -> None:
        src = VPN_CHANNEL.read_text(encoding="utf-8")
        # register(with:) must call seed (startup path that can surface TCC).
        m = re.search(
            r"static func register\(with messenger: FlutterBinaryMessenger\)\s*\{(?P<body>.*?)case \"connect\"",
            src,
            re.S,
        )
        self.assertIsNotNone(m, "could not locate register(with:) body")
        body = m.group("body")
        self.assertIn("seedAppGroupFromKnownSourcesIfNeeded", body)
        # Failures must not block channel setup / UI open.
        self.assertIn("try?", body)

    def test_suite_name_shared_prefs_same_group(self) -> None:
        channel = VPN_CHANNEL.read_text(encoding="utf-8")
        self.assertIn("UserDefaults(suiteName: RptSecrets.appGroupId)", channel)
        provider = (MACOS / "NativePrep" / "PacketTunnelProvider.swift").read_text(
            encoding="utf-8"
        )
        self.assertIn(GROUP_ID, provider)
        self.assertIn("UserDefaults(suiteName:", provider)

    def test_analysis_note_answers_three_questions(self) -> None:
        self.assertTrue(DOC.is_file(), f"missing analysis note {DOC}")
        text = DOC.read_text(encoding="utf-8").lower()
        self.assertIn("group.com.restoreprivacy.shared", text)
        self.assertIn("packet tunnel", text)
        # Not a third-party inventory claim.
        self.assertIn("not", text)
        self.assertTrue(
            "chrome" in text or "third-party" in text or "other mac apps" in text,
            "note should clarify non-third-party scope",
        )
        self.assertIn("open", text)
        self.assertIn("need", text)


if __name__ == "__main__":
    unittest.main()
