"""Structural proof: Android residual idle liveness tear (shipped sources).

Product contract: consecutive KEEPALIVE send failures always close the TUN
(clear full-tunnel routes) so the device is not blackholed. After tear, if the
user still wants Connect (desired), re-HELLO is scheduled with backoff —
Settings Auto-connect-if-idle (default off) only gates cold sticky restart,
not mid-session recovery after lock/Doze liveness loss.
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

    def test_ka_fail_streak_always_tears_tun(self) -> None:
        """Liveness loss must close TUN even when Auto-connect-if-idle is off."""
        self.assertIn("KEEPALIVE_FAIL_STREAK_RECONNECT", self.svc)
        # Tear gate must NOT require wantsIdleAutoReconnect (that was the blackhole bug).
        self.assertNotIn(
            "fails >= KEEPALIVE_FAIL_STREAK_RECONNECT && wantsIdleAutoReconnect()",
            self.svc,
        )
        self.assertIn(
            "if (fails >= KEEPALIVE_FAIL_STREAK_RECONNECT) {",
            self.svc,
        )
        # Within the KA fail branch, running is cleared and PFD closed.
        ka_idx = self.svc.index('thread(name = "rpt-keepalive"')
        ka_body = self.svc[ka_idx : ka_idx + 2200]
        fail_idx = ka_body.index("KEEPALIVE_FAIL_STREAK_RECONNECT")
        tear_window = ka_body[fail_idx : fail_idx + 550]
        self.assertIn("running.set(false)", tear_window)
        self.assertIn("pfd.close()", tear_window)
        # Idle-auto remains default OFF
        self.assertIn(
            "dualStackPref(context, KEY_AUTO_CONNECT_IF_IDLE, default = false)",
            self.prefs,
        )
        self.assertRegex(
            self.dart,
            r"autoConnectIfIdle\s*=\s*false",
        )

    def test_desired_session_recovery_after_tear_not_only_idle_auto(self) -> None:
        """Mid-session recovery uses wantsDesiredSessionRecovery (not idle-auto only)."""
        self.assertIn("fun wantsDesiredSessionRecovery", self.svc)
        self.assertIn("fun scheduleIdleReconnect", self.svc)
        self.assertIn("rpt-idle-reconnect", self.svc)
        self.assertIn("scheduleIdleReconnect(", self.svc)
        # scheduleIdleReconnect must gate on desired recovery, not idle-auto pref alone.
        sched = self.svc[
            self.svc.index("private fun scheduleIdleReconnect") : self.svc.index(
                "private fun scheduleIdleReconnect"
            )
            + 900
        ]
        self.assertIn("wantsDesiredSessionRecovery()", sched)
        self.assertNotIn("wantsIdleAutoReconnect()", sched)
        # Worker finally: still-desired → schedule re-HELLO; else clear desired + stop
        idx = self.svc.index("wantsDesiredSessionRecovery() -> {")
        window = self.svc[idx : idx + 500]
        self.assertIn("scheduleIdleReconnect", window)
        else_idx = self.svc.index("else -> {", idx)
        else_window = self.svc[else_idx : else_idx + 550]
        self.assertIn("setDesiredConnected", else_window)
        self.assertIn("stopSelf()", else_window)

    def test_disconnect_does_not_schedule_session_recovery(self) -> None:
        """Intentional Disconnect must not resurrect via desired recovery."""
        disc = self.svc[
            self.svc.index("ACTION_DISCONNECT") : self.svc.index("ACTION_DISCONNECT")
            + 550
        ]
        self.assertIn("userStopped.set(true)", disc)
        self.assertIn("desiredConnected = false", disc)
        self.assertIn("stopTunnel()", disc)
        self.assertNotIn("scheduleIdleReconnect", disc)

    def test_residual_wake_lock_for_lock_doze_keepalive(self) -> None:
        """Partial wake lock keeps lean KEEPALIVE schedulable under screen lock."""
        self.assertIn("PARTIAL_WAKE_LOCK", self.svc)
        self.assertIn("acquireResidualWakeLock", self.svc)
        self.assertIn("touchResidualWakeLock", self.svc)
        self.assertIn("releaseResidualWakeLock", self.svc)
        self.assertIn("rpt_residual_keepalive", self.svc)
        # Acquired when residual session becomes live; released in finally/stopTunnel.
        live = self.svc.index("isSessionActive = true")
        live_win = self.svc[live : live + 900]
        self.assertIn("acquireResidualWakeLock()", live_win)
        ka = self.svc[
            self.svc.index('thread(name = "rpt-keepalive"') : self.svc.index(
                'thread(name = "rpt-keepalive"'
            )
            + 900
        ]
        self.assertIn("touchResidualWakeLock()", ka)
        man = (
            ROOT
            / "client_app/android/app/src/main/AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        self.assertIn("android.permission.WAKE_LOCK", man)

    def test_cold_sticky_restart_still_gated_on_idle_auto(self) -> None:
        """Process death cold restart still requires Settings auto-connect-if-idle."""
        # Null-intent / sticky restart path in onStartCommand
        marker = 'when Settings "Auto connect if idle" is on'
        self.assertIn(marker, self.svc)
        else_branch = self.svc[
            self.svc.index(marker) - 200 : self.svc.index(marker) + 1600
        ]
        self.assertIn("autoConnectIfIdleEnabled", else_branch)
        self.assertIn("startTunnel(last.host", else_branch)

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
