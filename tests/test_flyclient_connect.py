"""Flyclient-style full-connect fast path decisions (pure unit tests)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.flyclient_connect import (  # noqa: E402
    FULL_CONNECT_CRITICAL_PATH,
    FullConnectStep,
    FlyclientConnectState,
    flyclient_critical_path_names,
    flyclient_decide_full_connect_work,
    flyclient_ordered_steps,
    flyclient_reuse_tunnel_plan,
)
from client.full_tunnel import (  # noqa: E402
    assert_full_tunnel_plan,
    build_full_tunnel_plan,
)
from client.connect import ConnectState, RptClient  # noqa: E402


class TestFlyclientDecide(unittest.TestCase):
    def test_cold_path_runs_all_critical_steps(self):
        plan = flyclient_decide_full_connect_work(FlyclientConnectState())
        self.assertFalse(plan.early_exit)
        self.assertEqual(plan.steps, list(FULL_CONNECT_CRITICAL_PATH))
        self.assertTrue(plan.needs_hello())
        self.assertTrue(plan.needs_residual_attach())
        self.assertEqual(plan.reason, "cold_full_connect")

    def test_already_residual_ready_early_exit(self):
        plan = flyclient_decide_full_connect_work(
            FlyclientConnectState(
                session_connected=True,
                session_vpn_ip="10.88.0.9",
                residual_routes_applied=True,
                residual_tun_up=True,
                has_if_index_or_iface=True,
                tunnel_plan_vpn_ip="10.88.0.9",
            )
        )
        self.assertTrue(plan.early_exit)
        self.assertEqual(plan.steps, [])
        self.assertEqual(set(plan.skipped), set(FULL_CONNECT_CRITICAL_PATH))
        self.assertFalse(plan.needs_hello())
        self.assertFalse(plan.needs_residual_attach())
        self.assertEqual(plan.reason, "already_residual_ready")

    def test_warm_session_skips_hello_keeps_routes(self):
        plan = flyclient_decide_full_connect_work(
            FlyclientConnectState(
                session_connected=True,
                session_vpn_ip="10.88.0.5",
                residual_routes_applied=False,
                residual_tun_up=False,
                has_if_index_or_iface=True,
                tunnel_plan_vpn_ip="10.88.0.5",
            )
        )
        self.assertFalse(plan.early_exit)
        self.assertFalse(plan.needs_hello())
        self.assertNotIn(FullConnectStep.HELLO_EXCHANGE, plan.steps)
        self.assertNotIn(FullConnectStep.BUILD_TUNNEL_PLAN, plan.steps)
        self.assertIn(FullConnectStep.ATTACH_TUN, plan.steps)
        self.assertIn(FullConnectStep.APPLY_ROUTES, plan.steps)
        self.assertTrue(plan.needs_residual_attach())

    def test_force_reconnect_ignores_warm_tip(self):
        plan = flyclient_decide_full_connect_work(
            FlyclientConnectState(
                session_connected=True,
                session_vpn_ip="10.88.0.5",
                residual_routes_applied=True,
                residual_tun_up=True,
                force_reconnect=True,
            )
        )
        self.assertFalse(plan.early_exit)
        self.assertEqual(plan.steps, list(FULL_CONNECT_CRITICAL_PATH))
        self.assertEqual(plan.reason, "force_reconnect")

    def test_ordered_steps_stable(self):
        messy = [
            FullConnectStep.APPLY_ROUTES,
            FullConnectStep.PREPARE_SECRETS,
            FullConnectStep.HELLO_EXCHANGE,
        ]
        ordered = flyclient_ordered_steps(messy)
        self.assertEqual(
            ordered,
            [
                FullConnectStep.PREPARE_SECRETS,
                FullConnectStep.HELLO_EXCHANGE,
                FullConnectStep.APPLY_ROUTES,
            ],
        )
        self.assertEqual(
            flyclient_critical_path_names()[0],
            FullConnectStep.PREPARE_SECRETS.value,
        )


class TestFlyclientPlanReuse(unittest.TestCase):
    def test_reuse_when_vpn_ip_matches(self):
        p1 = build_full_tunnel_plan("10.88.0.7")
        p2 = flyclient_reuse_tunnel_plan(p1, "10.88.0.7")
        self.assertIs(p2, p1)
        self.assertEqual(assert_full_tunnel_plan(p2), [])

    def test_rebuild_when_vpn_ip_changes(self):
        p1 = build_full_tunnel_plan("10.88.0.7")
        p2 = flyclient_reuse_tunnel_plan(p1, "10.88.0.8")
        self.assertIsNot(p2, p1)
        self.assertEqual(p2.tunnel_client_ip, "10.88.0.8")
        self.assertEqual(assert_full_tunnel_plan(p2), [])


class TestRptClientFlyclientConnect(unittest.TestCase):
    def test_connect_skips_hello_when_already_connected_residual_ready(self):
        client = RptClient()
        # Fake warm session without network
        from client.connect import ClientSession
        from node.crypto_session import SessionCrypto

        crypto = mock.Mock(spec=SessionCrypto)
        client.session = ClientSession(
            session_id=b"\x01" * 8,
            crypto=crypto,
            vpn_ip="10.88.0.3",
            endpoint=client.endpoint,
            pfs=True,
        )
        client.tunnel_plan = build_full_tunnel_plan("10.88.0.3")
        client.state = ConnectState.CONNECTED

        with mock.patch.object(client, "_status") as st:
            result = client.connect(residual_ready=True)
        self.assertTrue(result.ok)
        self.assertIn("already connected", result.message)
        st.assert_called()
        # Must not open UDP when residual-ready tip fires
        with mock.patch("client.connect.socket.socket") as sock_cls:
            client.connect(residual_ready=True)
            sock_cls.assert_not_called()


class TestStartFullTunnelPriorSkip(unittest.TestCase):
    """Drive real start_full_tunnel(..., prior=) skip on Windows/Linux helpers."""

    def _warm_client(self, vpn_ip: str = "10.88.0.11"):
        from client.connect import ClientSession
        from node.crypto_session import SessionCrypto

        client = RptClient()
        client.session = ClientSession(
            session_id=b"\x02" * 8,
            crypto=mock.Mock(spec=SessionCrypto),
            vpn_ip=vpn_ip,
            endpoint=client.endpoint,
            pfs=True,
        )
        client.tunnel_plan = build_full_tunnel_plan(vpn_ip)
        client.state = ConnectState.CONNECTED
        return client

    def test_windows_prior_same_plan_skips_tun_and_routes(self):
        from client.windows.tunnel_win import WindowsTunnelResult, start_full_tunnel

        client = self._warm_client()
        plan = client.tunnel_plan
        host = client.endpoint.host
        prior = WindowsTunnelResult(
            ok=True,
            message="prior residual",
            applied_commands=["route add 0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 12"],
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host=host,
            if_index=12,
        )
        with mock.patch(
            "client.windows.tunnel_win.create_windows_tun"
        ) as create_tun:
            out = start_full_tunnel(
                client,
                plan,
                host,
                require_system_capture=True,
                prior=prior,
            )
            create_tun.assert_not_called()
        self.assertTrue(out.ok)
        self.assertTrue(out.routes_applied)
        self.assertIn("flyclient skip", out.message)
        self.assertEqual(out.if_index, 12)

    def test_linux_prior_same_plan_skips_tun_and_routes(self):
        from client.linux.tunnel_linux import LinuxTunnelResult, start_full_tunnel

        client = self._warm_client()
        plan = client.tunnel_plan
        plan.tunnel_iface = "rpt0"
        host = client.endpoint.host
        prior = LinuxTunnelResult(
            ok=True,
            message="prior residual",
            applied_commands=["ip route add 0.0.0.0/1 dev rpt0"],
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host=host,
            iface="rpt0",
        )
        with mock.patch(
            "client.linux.tunnel_linux.create_linux_tun"
        ) as create_tun, mock.patch(
            "client.linux.tunnel_linux.resolve_default_route"
        ) as resolve:
            out = start_full_tunnel(
                client,
                plan,
                host,
                require_system_capture=True,
                prior=prior,
            )
            create_tun.assert_not_called()
            resolve.assert_not_called()
        self.assertTrue(out.ok)
        self.assertTrue(out.routes_applied)
        self.assertIn("flyclient skip", out.message)
        self.assertEqual(out.iface, "rpt0")


class TestProductAppsWireFlyclient(unittest.TestCase):
    def test_windows_app_work_passes_residual_ready_and_prior(self):
        src = (
            ROOT / "client" / "windows" / "app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("residual_ready=", src)
        self.assertIn("residual_ip_capture_active(prior)", src)
        self.assertIn("prior=prior if residual_ready else None", src)
        self.assertIn("physical_gw=phys_gw", src)
        self.assertIn("physical_default_gateway", src)

    def test_linux_app_work_passes_residual_ready_and_prior(self):
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("residual_ready=", src)
        self.assertIn("residual_ip_capture_active(prior)", src)
        self.assertIn("prior=prior if residual_ready else None", src)
        self.assertIn("prefetched_default_route=", src)
        self.assertIn("resolve_default_route", src)


if __name__ == "__main__":
    unittest.main()
