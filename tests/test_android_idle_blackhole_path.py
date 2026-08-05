"""Structural proof: Android residual idle blackhole path (shipped sources).

Root cause under investigation (analysis goal): TUN remains up with full routes
while RPT session/UDP is dead; KA tear is gated on Auto-connect-if-idle (default
off). These tests read real product sources — not reimplemented policy.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVC = (
    ROOT
    / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client"
    / "RptVpnService.kt"
)
ENGINE = (
    ROOT
    / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client"
    / "RptClientEngine.kt"
)
PREFS = (
    ROOT
    / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client"
    / "StartupPrefs.kt"
)
SETTINGS_DART = ROOT / "client_app/lib/settings_store.dart"
NODE_SESSIONS = ROOT / "node/sessions.py"
FULL_TUNNEL = ROOT / "client/full_tunnel.py"
KILL_SWITCH = ROOT / "client/kill_switch.py"


class TestAndroidIdleBlackholePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.svc = SVC.read_text(encoding="utf-8")
        cls.eng = ENGINE.read_text(encoding="utf-8")
        cls.prefs = PREFS.read_text(encoding="utf-8")
        cls.dart = SETTINGS_DART.read_text(encoding="utf-8")
        cls.node_sess = NODE_SESSIONS.read_text(encoding="utf-8")
        cls.full_tunnel = FULL_TUNNEL.read_text(encoding="utf-8")
        cls.kill_switch = KILL_SWITCH.read_text(encoding="utf-8")

    def test_shipped_sources_exist(self) -> None:
        for p in (SVC, ENGINE, PREFS, SETTINGS_DART, NODE_SESSIONS):
            self.assertTrue(p.is_file(), p)

    def test_full_tunnel_routes_install_default_capture(self) -> None:
        """Blackhole requires routes that capture all traffic while TUN is up."""
        self.assertIn('addRoute("0.0.0.0", 0)', self.svc)
        self.assertIn('addRoute("::", 0)', self.svc)
        # Residual IPv4 always on product path
        self.assertIn("RESIDUAL_IPV4_ALWAYS_ON = true", self.prefs)
        # Residual IPv6 default ON (ISP IPv6 also captured into dead tunnel)
        self.assertRegex(
            self.prefs,
            r"residualIpv6Enabled[\s\S]{0,120}default\s*=\s*true",
        )

    def test_no_setBlocking_call_on_builder(self) -> None:
        """Kill-switch fail-closed is not the primary blackhole mechanism."""
        # Strip line comments so the explanatory comment does not count as a call.
        code = re.sub(r"//.*?$", "", self.svc, flags=re.M)
        self.assertNotRegex(code, r"\.setBlocking\s*\(")
        # Python product mirror: residual builder is non-blocking
        from client.full_tunnel import android_vpn_builder_config, build_full_tunnel_plan
        from client.kill_switch import android_kill_switch_builder_flags

        plan = build_full_tunnel_plan("10.88.0.2")
        cfg = android_vpn_builder_config(plan)
        self.assertFalse(cfg.get("blocking"))
        self.assertFalse(cfg.get("killSwitch"))
        self.assertTrue(cfg.get("allowBypass"))
        flags = android_kill_switch_builder_flags()
        self.assertFalse(flags.get("blocking"))
        self.assertFalse(flags.get("killSwitch"))

    def test_keepalive_is_send_only_under_node_idle(self) -> None:
        self.assertIn("KEEPALIVE_INTERVAL_MS: Long = 25_000L", self.svc)
        self.assertIn("DEFAULT_SESSION_IDLE_SEC = 60.0", self.node_sess)
        self.assertIn("sealAndWrapKeepalive", self.svc)
        self.assertIn("dataSock.send", self.svc)
        # Engine only opens DATA (0x03); NODE_STATUS KA replies cannot prove liveness
        self.assertIn("0x03", self.eng)
        self.assertIn("inner[4] != 0x03.toByte()", self.eng)
        self.assertIn("fun packKeepalive", self.eng)
        self.assertIn("0x04", self.eng)

    def test_ka_fail_tears_tun_only_when_idle_auto_reconnect(self) -> None:
        """Primary product gap: default-off idle-auto leaves TUN up on KA failure."""
        self.assertIn("KEEPALIVE_FAIL_STREAK_RECONNECT", self.svc)
        # Exact gate from shipped Kotlin
        self.assertIn(
            "fails >= KEEPALIVE_FAIL_STREAK_RECONNECT && wantsIdleAutoReconnect()",
            self.svc,
        )
        # wantsIdleAutoReconnect requires Settings switch
        self.assertIn("autoConnectIfIdleEnabled", self.svc)
        # Defaults OFF — dual stack Kotlin + Flutter
        self.assertIn(
            "dualStackPref(context, KEY_AUTO_CONNECT_IF_IDLE, default = false)",
            self.prefs,
        )
        self.assertRegex(
            self.dart,
            r"autoConnectIfIdle\s*=\s*false",
        )

    def test_idle_auto_reconnect_is_separate_from_teardown_gate(self) -> None:
        """Reconnect scheduler exists but is only used when wantsIdleAutoReconnect."""
        self.assertIn("fun scheduleIdleReconnect", self.svc)
        self.assertIn("rpt-idle-reconnect", self.svc)
        # finally branch: idle-auto → schedule; else clear desired
        self.assertIn("scheduleIdleReconnect(", self.svc)
        idx = self.svc.index("wantsIdleAutoReconnect() -> {")
        window = self.svc[idx : idx + 400]
        self.assertIn("scheduleIdleReconnect", window)

    def test_post_establish_protect_still_required(self) -> None:
        """Protect is necessary but not sufficient for idle blackhole after session death."""
        self.assertIn("fun openProtectedNodeSocket", self.svc)
        self.assertIn("protect(s)", self.svc)
        self.assertIn("openProtectedNodeSocket(endpoint)", self.svc)

    def test_intentional_disconnect_tears_down(self) -> None:
        self.assertIn("ACTION_DISCONNECT", self.svc)
        disc = self.svc[
            self.svc.index("ACTION_DISCONNECT") : self.svc.index("ACTION_DISCONNECT")
            + 500
        ]
        self.assertIn("userStopped.set(true)", disc)
        self.assertIn("stopTunnel()", disc)


if __name__ == "__main__":
    unittest.main()
