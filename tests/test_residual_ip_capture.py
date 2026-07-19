"""Residual public IP must use the VPN node — not queue-only "Connected".

Evidence targets: dual /1 + Wintun required for product Connect success;
honest status when residual capture inactive; Disconnect tears routes down.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import build_full_tunnel_plan  # noqa: E402
from client.ui_theme import plain_tunnel_status  # noqa: E402
from client.windows.app import (  # noqa: E402
    auto_connect_on_launch_enabled,
    non_admin_connect_allowed,
    product_connect_requires_admin,
)
from client.windows.tunnel_win import (  # noqa: E402
    WindowsTunnelResult,
    product_tunnel_attach_active,
    residual_ip_capture_active,
    start_full_tunnel,
    stop_full_tunnel,
)


class TestResidualRouteGates(unittest.TestCase):
    """Product residual path fails closed without dual /1 system capture."""

    def test_residual_active_requires_routes_and_capture(self):
        plane = mock.Mock()
        plane.is_running.return_value = True
        self.assertFalse(residual_ip_capture_active(None))
        self.assertFalse(
            residual_ip_capture_active(
                WindowsTunnelResult(
                    True, "queue", [], dataplane=plane, routes_applied=False
                )
            )
        )
        self.assertFalse(
            residual_ip_capture_active(
                WindowsTunnelResult(
                    True,
                    "wintun no routes",
                    [],
                    dataplane=plane,
                    system_capture=True,
                    routes_applied=False,
                )
            )
        )
        self.assertTrue(
            residual_ip_capture_active(
                WindowsTunnelResult(
                    True,
                    "full",
                    [],
                    dataplane=plane,
                    system_capture=True,
                    routes_applied=True,
                )
            )
        )

    def test_require_system_capture_refuses_non_admin(self):
        client = mock.Mock()
        client.session = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.5")
        with mock.patch("client.windows.tunnel_win.is_admin", return_value=False):
            res = start_full_tunnel(
                client,
                plan,
                "104.156.224.47",
                prefer_system_capture=True,
                require_system_capture=True,
            )
        self.assertFalse(res.ok)
        self.assertFalse(res.routes_applied)
        self.assertFalse(residual_ip_capture_active(res))
        self.assertIn("Administrator", res.message)

    def test_require_system_capture_refuses_queue_only_success(self):
        client = mock.Mock()
        client.session = mock.Mock()
        client._sock = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.5")
        qtun = mock.Mock()
        qtun.name = "RPT"
        qtun.mode = "queue"
        qtun.configure_address.return_value = []
        plane = mock.Mock()
        plane.is_running.return_value = True

        with mock.patch("client.windows.tunnel_win.is_admin", return_value=True), mock.patch(
            "client.windows.tunnel_win.create_windows_tun",
            side_effect=RuntimeError("Wintun needs admin"),
        ), mock.patch("client.windows.tunnel_win.time.sleep"):
            res = start_full_tunnel(
                client,
                plan,
                "104.156.224.47",
                prefer_system_capture=True,
                require_system_capture=True,
            )
        self.assertFalse(res.ok)
        self.assertFalse(residual_ip_capture_active(res))
        self.assertIn("Wintun", res.message)

    def test_require_system_capture_fails_when_routes_not_applied(self):
        """Admin + capture TUN but dual /1 refused → product Connect fails (not fake Connected)."""
        client = mock.Mock()
        client.session = mock.Mock()
        client._sock = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.5")
        wtun = mock.Mock()
        wtun.name = "RPT"
        wtun.mode = "wintun"
        wtun.configure_address.return_value = []
        wtun.interface_index.return_value = 17
        plane = mock.Mock()
        plane.is_running.return_value = True

        with mock.patch("client.windows.tunnel_win.is_admin", return_value=True), mock.patch(
            "client.windows.tunnel_win.create_windows_tun", return_value=wtun
        ), mock.patch(
            "client.windows.tunnel_win.system_capture_ready", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.dataplane_enabled", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.RptDataPlane", return_value=plane
        ), mock.patch(
            "client.windows.tunnel_win.apply_routes_for_adapter",
            return_value=(["route add ..."], ["server pin failed: boom"], False),
        ), mock.patch(
            "client.windows.tunnel_win.time.sleep"
        ), mock.patch(
            "client.windows.tunnel_win.rollback_full_tunnel_routes", return_value=[]
        ):
            res = start_full_tunnel(
                client,
                plan,
                "104.156.224.47",
                prefer_system_capture=True,
                require_system_capture=True,
            )
        self.assertFalse(res.ok, res.message)
        self.assertFalse(res.routes_applied)
        self.assertFalse(residual_ip_capture_active(res))
        self.assertIn("Could not route", res.message)
        plane.stop.assert_called()
        wtun.close.assert_called()

    def test_queue_fallback_still_ok_without_require_system_capture(self):
        """Diagnostic / non-product path may attach queue dataplane without residual."""
        client = mock.Mock()
        client.session = mock.Mock()
        client._sock = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.5")
        qtun = mock.Mock()
        qtun.name = "RPT"
        qtun.mode = "queue"
        qtun.configure_address.return_value = []
        plane = mock.Mock()
        plane.is_running.return_value = True

        with mock.patch("client.windows.tunnel_win.is_admin", return_value=False), mock.patch(
            "client.windows.tunnel_win.create_windows_tun",
            side_effect=[RuntimeError("no wintun"), qtun],
        ), mock.patch(
            "client.windows.tunnel_win.system_capture_ready", return_value=False
        ), mock.patch(
            "client.windows.tunnel_win.dataplane_enabled", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.RptDataPlane", return_value=plane
        ), mock.patch(
            "client.windows.tunnel_win.time.sleep"
        ):
            res = start_full_tunnel(
                client,
                plan,
                "104.156.224.47",
                prefer_system_capture=True,
                require_system_capture=False,
            )
        self.assertTrue(res.ok, res.message)
        self.assertFalse(res.routes_applied)
        self.assertTrue(product_tunnel_attach_active(res))
        self.assertFalse(residual_ip_capture_active(res))


class TestResidualStatusHonesty(unittest.TestCase):
    def test_plain_status_does_not_claim_vpn_without_residual(self):
        s = plain_tunnel_status(
            "connected", vpn_ip="10.88.0.2", residual_capture=False
        )
        self.assertIn("ISP", s)
        self.assertNotIn("uses the VPN", s)
        ok = plain_tunnel_status(
            "connected", vpn_ip="10.88.0.2", residual_capture=True
        )
        self.assertIn("uses the VPN", ok)
        self.assertIn("10.88.0.2", ok)

    def test_product_policy_requires_admin_for_residual(self):
        self.assertTrue(product_connect_requires_admin())
        self.assertTrue(non_admin_connect_allowed())  # UI may open
        # Default settings: autoconnect off
        self.assertFalse(auto_connect_on_launch_enabled())

    def test_app_connect_uses_residual_not_queue_attach(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        conn = src[src.index("def _start_connect") : src.index("def _start_disconnect")]
        self.assertIn("require_system_capture=True", conn)
        self.assertIn("residual_ip_capture_active", conn)
        self.assertNotIn("product_tunnel_attach_active", conn)
        self.assertIn("elevate_if_needed", conn)
        self.assertIn("--rpt-auto-connect", conn)

    def test_main_resumes_after_user_elevate_flag(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        main = src[src.index("def main") :]
        self.assertIn("resume_after_elevate", main)
        self.assertIn("--rpt-auto-connect", main)
        self.assertIn("_resume_user_connect", main)
        # Default cold launch does not always connect (settings default off)
        self.assertFalse(auto_connect_on_launch_enabled())


class TestResidualDisconnect(unittest.TestCase):
    def test_stop_clears_routes_and_residual_flags(self):
        plan = build_full_tunnel_plan("10.88.0.5", tunnel_iface="RPT")
        server = "104.156.224.47"
        plane = mock.Mock()
        tun = mock.Mock()
        client = mock.Mock()
        result = WindowsTunnelResult(
            ok=True,
            message="up",
            applied_commands=[],
            tun=tun,
            dataplane=plane,
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host=server,
            if_index=17,
        )
        self.assertTrue(residual_ip_capture_active(result))
        with mock.patch(
            "client.windows.tunnel_win.rollback_full_tunnel_routes",
            return_value=["route delete 0.0.0.0 mask 128.0.0.0"],
        ) as rb:
            stop_full_tunnel(result, client)
        rb.assert_called_once()
        self.assertFalse(result.routes_applied)
        self.assertFalse(residual_ip_capture_active(result))
        plane.stop.assert_called_once()
        tun.close.assert_called_once()
        client.disconnect.assert_called_once()

    def test_disconnect_handler_tears_down(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        disc = src[src.index("def _start_disconnect") : src.index("def _open_upgrade")]
        self.assertTrue(
            "disconnect_full_tunnel" in disc or "_disconnect_tunnel" in disc
        )
        self.assertIn("def _disconnect_tunnel", src)
        self.assertIn("disconnect_full_tunnel", src)


if __name__ == "__main__":
    unittest.main()
