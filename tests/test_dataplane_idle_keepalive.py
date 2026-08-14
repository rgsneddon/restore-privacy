"""Residual idle keepalive policy — keep session under node prune without busy spin."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.dataplane import (  # noqa: E402
    IDLE_SELECT_MAX_S,
    KEEPALIVE_FAIL_THRESHOLD,
    KEEPALIVE_UNACKED_THRESHOLD,
    DataPlaneStats,
    RptDataPlane,
    residual_idle_select_max_s,
    residual_keepalive_interval_s,
    residual_keepalive_under_node_idle,
)
from client.connect import RptClient  # noqa: E402
from node.sessions import DEFAULT_SESSION_IDLE_SEC  # noqa: E402


class TestResidualKeepalivePolicy(unittest.TestCase):
    def test_interval_strictly_under_node_idle(self):
        interval = residual_keepalive_interval_s()
        self.assertTrue(residual_keepalive_under_node_idle(interval))
        self.assertLess(interval, DEFAULT_SESSION_IDLE_SEC)
        self.assertGreaterEqual(interval, 10.0)
        self.assertLessEqual(interval, 25.0)
        # Explicit node idle 60 → ~20
        self.assertEqual(residual_keepalive_interval_s(60.0), 20.0)
        self.assertTrue(residual_keepalive_under_node_idle(20.0, 60.0))
        self.assertFalse(residual_keepalive_under_node_idle(60.0, 60.0))
        self.assertFalse(residual_keepalive_under_node_idle(90.0, 60.0))

    def test_idle_select_max_bounded_no_busy_spin(self):
        self.assertEqual(residual_idle_select_max_s(), IDLE_SELECT_MAX_S)
        self.assertGreaterEqual(IDLE_SELECT_MAX_S, 0.2)
        self.assertLessEqual(IDLE_SELECT_MAX_S, 1.0)
        src = (ROOT / "client" / "dataplane.py").read_text(encoding="utf-8")
        # Must sleep/select with idle backoff — not a tight empty loop
        self.assertIn("select.select", src)
        self.assertIn("idle_select_s", src)
        self.assertIn("IDLE_SELECT_MAX_S", src)
        # Keepalive independent of cover traffic
        self.assertIn("send_keepalive", src)
        self.assertIn("keepalives_sent", src)

    def test_default_interval_less_than_legacy_30s_and_node_60(self):
        """NAT-friendly interval: not equal to node idle or a 30s cliff."""
        interval = residual_keepalive_interval_s(DEFAULT_SESSION_IDLE_SEC)
        self.assertLess(interval, 30.0)
        self.assertLess(interval, DEFAULT_SESSION_IDLE_SEC)


class TestSendKeepaliveReturn(unittest.TestCase):
    def test_send_keepalive_returns_bool_success(self):
        client = RptClient.__new__(RptClient)
        mock_sock = mock.Mock()
        mock_sock.sendto.return_value = 16
        client._sock = mock_sock
        client.session = mock.Mock(session_id=b"\x02" * 8)
        from client.endpoint import Endpoint

        client.endpoint = Endpoint("127.0.0.1", 44044)
        self.assertTrue(client.send_keepalive())
        mock_sock.sendto.assert_called()

    def test_send_keepalive_false_without_session(self):
        client = RptClient.__new__(RptClient)
        client._sock = mock.Mock()
        client.session = None
        client.endpoint = None
        self.assertFalse(client.send_keepalive())

    def test_send_keepalive_false_on_oserror(self):
        client = RptClient.__new__(RptClient)
        mock_sock = mock.Mock()
        mock_sock.sendto.side_effect = OSError("network down")
        client._sock = mock_sock
        client.session = mock.Mock(session_id=b"\x03" * 8)
        from client.endpoint import Endpoint

        client.endpoint = Endpoint("127.0.0.1", 44044)
        self.assertFalse(client.send_keepalive())


class TestDataPlaneKeepaliveScheduling(unittest.TestCase):
    def test_plane_uses_policy_interval_under_node_idle(self):
        client = RptClient.__new__(RptClient)
        client.session = mock.Mock(session_id=b"\x01" * 8, crypto=mock.Mock())
        client.session.crypto.traffic_shape = None
        client._sock = mock.Mock()
        client.endpoint = mock.Mock(address=("127.0.0.1", 44044))
        client.send_keepalive = mock.Mock(return_value=True)
        client.open_packet_allow_cover = mock.Mock(return_value=(None, True))
        client.seal_packet = mock.Mock(return_value=b"x")
        client.process_node_status_frame = mock.Mock()

        plane = RptDataPlane(client, keepalive_interval_s=15.0)
        self.assertEqual(plane._keepalive_interval_s, 15.0)
        self.assertTrue(residual_keepalive_under_node_idle(plane._keepalive_interval_s))

    def test_liveness_lost_after_threshold_failures(self):
        client = RptClient.__new__(RptClient)
        client.session = mock.Mock(session_id=b"\x01" * 8, crypto=mock.Mock())
        client.session.crypto.traffic_shape = None
        sock = mock.Mock()
        sock.recvfrom.side_effect = BlockingIOError
        # Real select needs int fileno — keep sock off the select list via patch.
        client._sock = sock
        client.endpoint = mock.Mock(address=("127.0.0.1", 44044))
        client.send_keepalive = mock.Mock(return_value=False)
        client.open_packet_allow_cover = mock.Mock(return_value=(None, False))
        client.seal_packet = mock.Mock()
        client.process_node_status_frame = mock.Mock()

        lost = []

        class FakeTun:
            def read_packet(self, max_size=65535):
                return None

            def write_packet(self, packet):
                pass

            def fileno(self):
                return -1

            def close(self):
                pass

        with mock.patch("client.dataplane.select.select", return_value=([], [], [])):
            plane = RptDataPlane(
                client,
                keepalive_interval_s=0.05,
                on_liveness_lost=lambda: lost.append(1),
            )
            plane.start(FakeTun())
            # Allow several keepalive periods + threshold failures
            deadline = time.time() + 3.0
            while time.time() < deadline and not plane.stats.session_liveness_lost:
                time.sleep(0.05)
            plane.stop()
        self.assertTrue(plane.stats.session_liveness_lost)
        self.assertGreaterEqual(
            plane.stats.consecutive_keepalive_failures, KEEPALIVE_FAIL_THRESHOLD
        )
        self.assertGreaterEqual(plane.stats.keepalives_failed, KEEPALIVE_FAIL_THRESHOLD)
        self.assertTrue(lost, "on_liveness_lost must fire")

    def test_send_ok_without_peer_reply_marks_liveness_lost(self):
        """OS accepted keepalive UDP but no NODE_STATUS/DATA → idle-dead."""
        client = RptClient.__new__(RptClient)
        client.session = mock.Mock(session_id=b"\x01" * 8, crypto=mock.Mock())
        client.session.crypto.traffic_shape = None
        sock = mock.Mock()
        sock.recvfrom.side_effect = BlockingIOError
        client._sock = sock
        client.endpoint = mock.Mock(address=("127.0.0.1", 44044))
        client.send_keepalive = mock.Mock(return_value=True)
        client.open_packet_allow_cover = mock.Mock(return_value=(None, False))
        client.seal_packet = mock.Mock()
        client.process_node_status_frame = mock.Mock()

        lost = []

        class FakeTun:
            def read_packet(self, max_size=65535, wait_ms=0):
                return None

            def write_packet(self, packet):
                pass

            def fileno(self):
                return -1

            def close(self):
                pass

        with mock.patch("client.dataplane.select.select", return_value=([], [], [])):
            plane = RptDataPlane(
                client,
                keepalive_interval_s=0.05,
                on_liveness_lost=lambda: lost.append(1),
            )
            plane.start(FakeTun())
            deadline = time.time() + 3.0
            while time.time() < deadline and not plane.stats.session_liveness_lost:
                time.sleep(0.05)
            plane.stop()
        self.assertTrue(plane.stats.session_liveness_lost)
        self.assertGreaterEqual(
            plane.stats.consecutive_keepalive_unacked, KEEPALIVE_UNACKED_THRESHOLD
        )
        self.assertTrue(lost, "idle-dead restore hook must fire")

    def test_successful_keepalive_resets_failure_streak(self):
        client = RptClient.__new__(RptClient)
        client.session = mock.Mock(session_id=b"\x01" * 8, crypto=mock.Mock())
        client.session.crypto.traffic_shape = None
        from node.protocol import MAGIC, MsgType

        sock = mock.Mock()
        ns = MAGIC + bytes([int(MsgType.NODE_STATUS)]) + b"\x00" * 16

        def _recv(*_a, **_k):
            n = getattr(_recv, "n", 0)
            _recv.n = n + 1
            if n % 2 == 0:
                return ns, ("127.0.0.1", 44044)
            raise BlockingIOError

        sock.recvfrom.side_effect = _recv
        client._sock = sock
        client.endpoint = mock.Mock(address=("127.0.0.1", 44044))
        # Fail twice then succeed forever
        results = [False, False, True, True, True, True, True, True]
        client.send_keepalive = mock.Mock(
            side_effect=lambda: results.pop(0) if results else True
        )
        client.open_packet_allow_cover = mock.Mock(return_value=(None, False))
        client.seal_packet = mock.Mock()
        client.process_node_status_frame = mock.Mock()

        class FakeTun:
            def read_packet(self, max_size=65535):
                return None

            def write_packet(self, packet):
                pass

            def fileno(self):
                return -1

            def close(self):
                pass

        with mock.patch("client.dataplane.select.select", return_value=([], [], [])):
            plane = RptDataPlane(client, keepalive_interval_s=0.05)
            plane.start(FakeTun())
            time.sleep(0.6)
            plane.stop()
        self.assertFalse(plane.stats.session_liveness_lost)
        self.assertGreaterEqual(plane.stats.keepalives_sent, 1)
        self.assertEqual(plane.stats.consecutive_keepalive_failures, 0)


class TestWindowsIdleRestoreWiring(unittest.TestCase):
    def test_tunnel_win_wires_liveness_lost_restore(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("on_liveness_lost", src)
        self.assertIn("_on_residual_liveness_lost", src)
        self.assertIn("restore_windows_residual_path", src)
        self.assertIn("session_liveness_lost", src)

    def test_residual_honesty_false_when_liveness_lost(self):
        from client.windows.tunnel_win import (
            WindowsTunnelResult,
            residual_ip_capture_active,
        )
        from client.full_tunnel import build_full_tunnel_plan

        plan = build_full_tunnel_plan("10.88.0.9", tunnel_iface="RPT")

        class DeadPlane:
            stats = DataPlaneStats(session_liveness_lost=True, started=True)

            def is_running(self):
                return True

        res = WindowsTunnelResult(
            ok=True,
            message="dead idle",
            applied_commands=[],
            dataplane=DeadPlane(),  # type: ignore[arg-type]
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host="1.2.3.4",
            if_index=17,
        )
        self.assertFalse(residual_ip_capture_active(res))


if __name__ == "__main__":
    unittest.main()
