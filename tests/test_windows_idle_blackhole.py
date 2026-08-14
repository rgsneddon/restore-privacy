"""Windows residual idle-dead must not leave dual /1 black-holing internet.

Drives shipped attach-ready, capture-active, keepalive, liveness, and restore.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.dataplane import (  # noqa: E402
    KEEPALIVE_FAIL_THRESHOLD,
    KEEPALIVE_UNACKED_THRESHOLD,
    DataPlaneStats,
    apply_keepalive_liveness_tick,
    residual_idle_dead,
    residual_keepalive_interval_s,
    residual_keepalive_under_node_idle,
)
from client.full_tunnel import (  # noqa: E402
    build_full_tunnel_plan,
    windows_residual_restore_route_commands,
)
from node.sessions import DEFAULT_SESSION_IDLE_SEC  # noqa: E402


class TestKeepaliveShorterThanNodePrune(unittest.TestCase):
    def test_interval_strictly_under_node_idle(self) -> None:
        interval = residual_keepalive_interval_s()
        self.assertTrue(residual_keepalive_under_node_idle(interval))
        self.assertLess(interval, DEFAULT_SESSION_IDLE_SEC)
        self.assertLess(interval, float(DEFAULT_SESSION_IDLE_SEC))


class TestIdleDeadNotCaptureActive(unittest.TestCase):
    def test_live_dataplane_with_return_stays_capture_active(self) -> None:
        from client.windows.tunnel_win import (
            WindowsTunnelResult,
            residual_ip_capture_active,
            residual_post_attach_ready,
        )

        self.assertTrue(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=True,
                keepalive_ok=True,
                forward_path_ok=True,
                dns_ok=True,
                dataplane_return_ok=True,
                session_liveness_lost=False,
            )
        )
        plan = build_full_tunnel_plan("10.88.0.9", tunnel_iface="RPT")

        class LivePlane:
            stats = DataPlaneStats(
                session_liveness_lost=False,
                started=True,
                udp_to_tun=4,
                keepalives_sent=2,
            )

            def is_running(self) -> bool:
                return True

        res = WindowsTunnelResult(
            ok=True,
            message="up",
            applied_commands=[],
            dataplane=LivePlane(),  # type: ignore[arg-type]
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host="203.0.113.10",
            if_index=17,
        )
        self.assertFalse(residual_idle_dead(LivePlane.stats, routes_applied=True))
        self.assertTrue(residual_ip_capture_active(res))

    def test_session_liveness_lost_is_not_capture_active(self) -> None:
        from client.windows.tunnel_win import (
            WindowsTunnelResult,
            residual_ip_capture_active,
            residual_post_attach_ready,
        )

        self.assertFalse(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=True,
                keepalive_ok=True,
                forward_path_ok=True,
                dns_ok=True,
                dataplane_return_ok=True,
                session_liveness_lost=True,
            )
        )
        plan = build_full_tunnel_plan("10.88.0.9", tunnel_iface="RPT")

        class DeadPlane:
            stats = DataPlaneStats(session_liveness_lost=True, started=True)

            def is_running(self) -> bool:
                return True

        res = WindowsTunnelResult(
            ok=True,
            message="idle-dead",
            applied_commands=[],
            dataplane=DeadPlane(),  # type: ignore[arg-type]
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host="203.0.113.10",
            if_index=17,
        )
        self.assertTrue(residual_idle_dead(DeadPlane.stats, routes_applied=True))
        self.assertFalse(residual_ip_capture_active(res))

    def test_no_data_return_without_smokes_is_not_ready(self) -> None:
        from client.windows.tunnel_win import residual_post_attach_ready

        self.assertFalse(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=True,
                keepalive_ok=True,
                forward_path_ok=False,
                dns_ok=False,
                require_forward_smoke=False,
                require_dns_smoke=False,
                dataplane_return_ok=False,
                session_liveness_lost=False,
            )
        )


class TestKeepaliveUnackedMarksIdleDead(unittest.TestCase):
    def test_send_ok_without_peer_reply_loses_liveness(self) -> None:
        stats = DataPlaneStats()
        just = False
        for i in range(KEEPALIVE_UNACKED_THRESHOLD):
            just = apply_keepalive_liveness_tick(
                stats, send_ok=True, peer_seen_since_last=False
            )
        self.assertTrue(just)
        self.assertTrue(stats.session_liveness_lost)
        self.assertEqual(
            stats.consecutive_keepalive_unacked, KEEPALIVE_UNACKED_THRESHOLD
        )
        self.assertTrue(residual_idle_dead(stats, routes_applied=True))

    def test_peer_reply_resets_unacked_streak(self) -> None:
        stats = DataPlaneStats()
        apply_keepalive_liveness_tick(
            stats, send_ok=True, peer_seen_since_last=False
        )
        just = apply_keepalive_liveness_tick(
            stats, send_ok=True, peer_seen_since_last=True
        )
        self.assertFalse(just)
        self.assertFalse(stats.session_liveness_lost)
        self.assertEqual(stats.consecutive_keepalive_unacked, 0)

    def test_send_failures_still_trip_fail_threshold(self) -> None:
        stats = DataPlaneStats()
        just = False
        for _ in range(KEEPALIVE_FAIL_THRESHOLD):
            just = apply_keepalive_liveness_tick(
                stats, send_ok=False, peer_seen_since_last=False
            )
        self.assertTrue(just)
        self.assertTrue(stats.session_liveness_lost)
        self.assertGreaterEqual(
            stats.consecutive_keepalive_failures, KEEPALIVE_FAIL_THRESHOLD
        )


class TestIdleLostRestoreClearsCapture(unittest.TestCase):
    def test_restore_hook_reports_residual_path_restore(self) -> None:
        from client.windows.tunnel_win import residual_idle_lost_restore

        cmds = windows_residual_restore_route_commands("203.0.113.10")
        self.assertTrue(any("128.0.0.0" in c for c in cmds))
        with mock.patch(
            "client.windows.tunnel_win._run_cmds",
            return_value=(["route delete 0.0.0.0 mask 128.0.0.0"], []),
        ):
            with mock.patch("client.windows.tunnel_win.residual_shell_run"):
                with mock.patch(
                    "client.windows.tunnel_win.rollback_ipv6_leak_mitigation",
                    return_value=[],
                ):
                    with mock.patch(
                        "client.windows.firewall_allow.apply_windows_fw_allows",
                        return_value=([], True, []),
                    ):
                        report = residual_idle_lost_restore(
                            server_host="203.0.113.10",
                            plan=build_full_tunnel_plan(
                                "10.88.0.9", tunnel_iface="RPT"
                            ),
                            if_index=17,
                        )
        self.assertTrue(report["residual_path_restored"])
        self.assertTrue(report["clears_dual_slash1"])
        self.assertTrue(report["kill_switch_rollback"])
        applied = list(report["applied"])  # type: ignore[arg-type]
        self.assertTrue(any("128.0.0.0" in str(c) for c in applied))

    def test_liveness_lost_hook_calls_idle_restore(self) -> None:
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        lost = src.index("def _on_residual_liveness_lost")
        chunk = src[lost : lost + 900]
        self.assertIn("residual_idle_lost_restore", chunk)
        self.assertIn("routes_applied", chunk)


if __name__ == "__main__":
    unittest.main()
