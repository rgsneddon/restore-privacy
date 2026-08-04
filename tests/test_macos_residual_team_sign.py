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
        # Residual host shares App Group with PacketTunnel for secrets/prefs seed.
        stripped = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        self.assertIn("application-groups", stripped)
        self.assertIn("group.com.restoreprivacy.shared", stripped)

    def test_host_seeds_home_and_app_group_for_appex(self):
        secrets = MAC / "NativePrep" / "RptSecrets.swift"
        channel = CHANNEL
        s = secrets.read_text(encoding="utf-8")
        c = channel.read_text(encoding="utf-8")
        self.assertIn("seedHomeRestorePrivacyFromKnownSourcesIfNeeded", s)
        self.assertIn("seedAppGroupFromKnownSourcesIfNeeded", s)
        self.assertIn(".restore-privacy", s)
        self.assertIn("seedHomeRestorePrivacyFromKnownSourcesIfNeeded", c)
        # Unreadable secret dirs must not abort load (permission fallback).
        self.assertIn("isReadableFile", s)
        # Appex still has App Group + home temporary-exception
        appex = APPEX_ENT.read_text(encoding="utf-8")
        self.assertIn("group.com.restoreprivacy.shared", appex)
        self.assertIn("temporary-exception.files.home-relative-path.read-only", appex)
        self.assertIn(".restore-privacy/", appex)

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
        # NE permission / host-only HELLO: open System Settings for user Allow
        self.assertIn("openVpnSystemSettings", text)
        self.assertIn("vpnSystemSettingsURLCandidates", text)
        self.assertIn("openVpnSettings", text)
        self.assertIn("needsVpnSystemSettingsApproval", text)
        self.assertIn("Network-Settings.extension", text)
        self.assertIn("annotateNeedsVpnSettings", text)
        # Pre-Connect Packet Tunnel registration (not L2TP/IKEv2)
        self.assertIn("preparePacketTunnelConfiguration", text)
        self.assertIn("prepareVpn", text)
        self.assertIn("applyProductPacketTunnelProtocol", text)
        self.assertIn("productTunnelType", text)
        self.assertIn("packet-tunnel", text)
        self.assertIn("NETunnelProviderProtocol", text)
        self.assertNotIn("NEVPNProtocolL2TP", text)
        self.assertNotIn("NEVPNProtocolIKEv2", text)
        self.assertNotIn("NEVPNProtocolIPSec", text)
        # Debounce only after successful prepare — never stamp success on failure
        self.assertIn("lastSuccessfulPrepareAt", text)
        self.assertNotIn("lastPrepareAt", text)
        # lastSuccessfulPrepareAt = Date() only on manager success path
        success_stamp = text.find("lastSuccessfulPrepareAt = Date()")
        self.assertGreater(success_stamp, 0)
        # Must appear after "if let manager" success branch, not before loadOrCreateManager callback body as unconditional
        prepare_fn = text.find("func preparePacketTunnelConfiguration")
        self.assertGreater(prepare_fn, 0)
        # Failure path must not assign lastSuccessfulPrepareAt before return of prepared:false
        fail_marker = 'prepared": false'
        # Ensure we do not set lastSuccessfulPrepareAt immediately at start of callback (old bug)
        callback_start = text.find(
            "loadOrCreateManager(host: host, port: port) { manager, neError in",
            prepare_fn,
        )
        self.assertGreater(callback_start, 0)
        # Between callback open and "if let manager", must NOT assign lastSuccessfulPrepareAt
        if_let = text.find("if let manager {", callback_start)
        self.assertGreater(if_let, callback_start)
        between = text[callback_start:if_let]
        self.assertNotIn(
            "lastSuccessfulPrepareAt = Date()",
            between,
            "must not stamp lastSuccessfulPrepareAt before success branch",
        )

    def test_preconnect_prepare_wired_from_flutter_launch_path(self):
        """Launch/first-run calls prepare before Connect is the productive path."""
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        vpn = (ROOT / "client_app" / "lib" / "vpn_controller.dart").read_text(
            encoding="utf-8"
        )
        status = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        # Shipped path: sequenced prepare + channel preparePacketTunnelConfiguration.
        self.assertIn("preparePacketTunnelConfiguration", vpn)
        self.assertIn("preparePacketTunnelSequenced", vpn)
        self.assertIn("prepareVpn", vpn)
        self.assertIn("_prepareApplePacketTunnelBeforeConnect", main)
        self.assertIn("preparePacketTunnelSequenced", main)
        self.assertIn("kProductVpnTunnelType", status)
        self.assertIn("packet-tunnel", status)
        self.assertIn("kProductVpnProviderBundleId", status)
        # Product copy must not instruct adding legacy manual VPN types
        combined = (status + main).lower()
        self.assertIn("do not add l2tp", combined)
        self.assertIn("isProductPacketTunnelPrepareResult", status)
        self.assertIn("mapPrepareVpnStatusMessage", status)

    def test_honesty_message_mentions_team_residual_and_system_settings(self):
        dart = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("System VPN (Packet Tunnel) did not become active", dart)
        # Free monopin residual-capable path: Allow first; Team residual only on
        # explicit missing-host-NE copy (kMissingHostNeEntitlementMessage).
        self.assertIn("kMissingHostNeEntitlementMessage", dart)
        self.assertIn("sign_macos_residual_team", dart)
        self.assertIn("VPN & Filters", dart)
        # kPacketTunnelNotActiveMessage must not lead with Team residual re-sign.
        start = dart.index("kPacketTunnelNotActiveMessage")
        end = dart.index("kHostOnlyHelloNotFullTunnelMessage", start)
        pt_msg = dart[start:end]
        self.assertNotIn("sign_macos_residual_team", pt_msg)
        self.assertIn("shouldPromptOpenVpnSystemSettings", dart)
        self.assertIn("shouldShowOpenVpnSettingsControl", dart)
        self.assertIn("isNeVpnPermissionFailureMessage", dart)
        self.assertIn("isOpenVpnSettingsFeedbackMessage", dart)
        self.assertIn("kOpenVpnSettingsLabel", dart)
        self.assertIn("kOpenVpnSettingsOpenedFeedback", dart)
        self.assertIn("kOpenVpnSettingsFailedFeedback", dart)
        # Open feedback must not be the sole residual status (sticky control contract)
        self.assertIn("reportStatus", (
            ROOT / "client_app" / "lib" / "vpn_controller.dart"
        ).read_text(encoding="utf-8"))

        swift = (
            ROOT
            / "client_app"
            / "apple_shared"
            / "Rpt2"
            / "Sources"
            / "Rpt2"
            / "RptFullTunnelResult.swift"
        ).read_text(encoding="utf-8")
        # Missing-host-NE string keeps developer re-sign; residual-capable PT message does not.
        self.assertIn("missingHostNeEntitlementMessage", swift)
        self.assertIn("sign_macos_residual_team", swift)
        self.assertIn("VPN & Filters", swift)
        pt_start = swift.index("packetTunnelNotActiveMessage")
        pt_end = swift.index("hostOnlyHelloNotFullTunnelMessage", pt_start)
        self.assertNotIn("sign_macos_residual_team", swift[pt_start:pt_end])

    def test_open_vpn_settings_candidates_are_shipped_urls(self):
        """Shipped helper lists real macOS Settings deep-links (no live UI required)."""
        text = CHANNEL.read_text(encoding="utf-8")
        # Candidate list is pure data inside open helper
        for needle in (
            "x-apple.systempreferences:com.apple.Network-Settings.extension",
            "x-apple.systempreferences:com.apple.preference.network",
            "x-apple.systempreferences:com.apple.LoginItems-Settings.extension",
            "Network.prefPane",
        ):
            self.assertIn(needle, text, f"missing settings candidate: {needle}")

    def test_prepare_detects_host_missing_packet_tunnel_entitlement(self):
        """Prepare must refuse registration when host lacks packet-tunnel-provider.

        Public DevID host omits NE so AMFI does not kill launch; residual
        registration then fails unless Team residual re-sign is applied.
        """
        text = CHANNEL.read_text(encoding="utf-8")
        for needle in (
            "hostHasPacketTunnelNetworkExtensionEntitlement",
            "hostMissingNeEntitlementMessage",
            "needsTeamResidualSign",
            "packet-tunnel-provider",
            "sign_macos_residual_team.py",
            # After save, re-assert isEnabled so Network settings is not stuck inactive
            "Packet Tunnel saved but remains disabled",
        ):
            self.assertIn(needle, text, f"missing prepare residual contract: {needle}")
        # loadOrCreateManager gates on host entitlement before loadAllFromPreferences
        self.assertLess(
            text.index("hostHasPacketTunnelNetworkExtensionEntitlement"),
            text.index("loadAllFromPreferences"),
        )

    def test_disconnect_stops_system_network_vpn(self):
        """Disconnect must stopVPNTunnel and wait for system VPN down."""
        text = CHANNEL.read_text(encoding="utf-8")
        for needle in (
            "stopAllTunnels",
            "stopVPNTunnel",
            "issueStopOnManagers",
            "waitUntilManagersDisconnected",
            "systemVpnStopped",
            "shouldStopManager",
            # Broader match so Network row always tears down
            "restorePrivacyClient",
            "case \"status\"",
        ):
            self.assertIn(needle, text, f"missing disconnect system-stop: {needle}")

    def test_connect_enables_system_vpn_then_starts_tunnel(self):
        """Connect must re-register/enable Network VPN and startTunnel in tandem."""
        text = CHANNEL.read_text(encoding="utf-8")
        for needle in (
            "enableProductVpnAndStartTunnel",
            "reloadProductManager",
            "ensureEnabledThenStartTunnel",
            "isProductManager",
            "lastSuccessfulPrepareAt = nil",
            "startTunnel(options:",
            # User-deleted config is recreated on Connect
            "re-registers the system VPN profile",
            # Network toggle turns on with startTunnel when allowed
            "enables the system VPN connection in Network settings",
        ):
            self.assertIn(needle, text, f"missing connect tandem path: {needle}")
        # Product manager matching must not hijack empty-provider rows
        self.assertIn("bid == providerBundleId", text)
        # Connect entry calls enable helper (not bare loadOrCreate alone)
        connect_fn = text.split("private static func connect(", 1)[1].split(
            "private static func enableProductVpnAndStartTunnel", 1
        )[0]
        self.assertIn("enableProductVpnAndStartTunnel", connect_fn)

    def test_catalog_handoff_and_build_docs_name_team_residual_resign(self):
        """Operator-facing residual docs: Packet Tunnel residual needs Team re-sign."""
        handoff = (ROOT / "client_app" / "APPLE_HANDOFF_0.3.4.md").read_text(
            encoding="utf-8"
        )
        build = (ROOT / "client_app" / "APPLE_BUILD.md").read_text(encoding="utf-8")
        for label, text in (("APPLE_HANDOFF_0.3.4.md", handoff), ("APPLE_BUILD.md", build)):
            with self.subTest(doc=label):
                self.assertIn("scripts/sign_macos_residual_team.py", text)
                self.assertIn("Team residual", text)
                # Public DevID path is not full host NE residual
                self.assertRegex(
                    text,
                    r"(?i)(omit|omits|without|not).{0,80}(host).{0,40}(network extension|NE)",
                )


if __name__ == "__main__":
    unittest.main()
