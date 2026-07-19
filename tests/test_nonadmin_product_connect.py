"""Product residual Connect: elevation + Wintun dual /1 (not queue-as-Connected).

Queue attach remains available for diagnostics when require_system_capture=False.
Product UI only reports Connected when residual_ip_capture_active.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import build_full_tunnel_plan  # noqa: E402
from client.windows.app import (  # noqa: E402
    auto_connect_on_launch_enabled,
    non_admin_connect_allowed,
    product_connect_requires_admin,
)
from client.windows.tunnel_win import (  # noqa: E402
    product_tunnel_attach_active,
    residual_ip_capture_active,
    start_full_tunnel,
    WindowsTunnelResult,
)


class TestResidualProductConnectPolicy(unittest.TestCase):
    def test_policy_residual_needs_admin(self):
        # UI may open without admin; product residual success requires elevation
        self.assertTrue(non_admin_connect_allowed())
        self.assertTrue(product_connect_requires_admin())
        self.assertFalse(auto_connect_on_launch_enabled())

    def test_product_require_system_capture_blocks_queue_connected(self):
        client = mock.Mock()
        client.session = mock.Mock()
        client._sock = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.5")
        with mock.patch("client.windows.tunnel_win.is_admin", return_value=False):
            res = start_full_tunnel(
                client,
                plan,
                "82.221.101.241",
                prefer_system_capture=True,
                require_system_capture=True,
            )
        self.assertFalse(res.ok)
        self.assertFalse(residual_ip_capture_active(res))
        self.assertIn("Administrator", res.message)

    def test_diagnostic_queue_fallback_without_require(self):
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
            side_effect=[RuntimeError("Wintun needs admin"), qtun],
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
                "82.221.101.241",
                prefer_system_capture=True,
                require_system_capture=False,
            )

        self.assertTrue(res.ok, res.message)
        self.assertFalse(res.routes_applied)
        self.assertTrue(product_tunnel_attach_active(res))
        self.assertFalse(residual_ip_capture_active(res))

    def test_product_attach_helpers(self):
        plane = mock.Mock()
        plane.is_running.return_value = True
        self.assertFalse(product_tunnel_attach_active(None))
        self.assertTrue(
            product_tunnel_attach_active(
                WindowsTunnelResult(True, "up", [], dataplane=plane)
            )
        )
        self.assertFalse(
            residual_ip_capture_active(
                WindowsTunnelResult(True, "up", [], dataplane=plane)
            )
        )

    def test_app_connect_gates_on_residual_and_elevate(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("residual_ip_capture_active", src)
        self.assertIn("require_system_capture=True", src)
        self.assertIn("non_admin_connect_allowed", src)
        self.assertNotIn("def _auto_connect", src)
        conn = src[src.index("def _start_connect") : src.index("def _start_disconnect")]
        self.assertIn("start_full_tunnel", conn)
        self.assertIn("residual_ip_capture_active", conn)
        self.assertIn("elevate_if_needed", conn)
        self.assertIn("--rpt-auto-connect", conn)
        # Launch message must not claim non-admin residual success
        main = src[src.index("def main") :]
        self.assertNotIn(
            "Connect still works without Administrator (session + dataplane).",
            main,
        )

    def test_tunnel_source_queue_fallback_only_when_not_required(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        self.assertIn("force_queue=True", src)
        self.assertIn("using in-process dataplane", src)
        self.assertIn("require_system_capture", src)
        self.assertIn("residual_ip_capture_active", src)


if __name__ == "__main__":
    unittest.main()
