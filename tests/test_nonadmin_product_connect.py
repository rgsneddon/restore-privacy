"""Product Connect without Run as administrator — queue TUN + dataplane attach."""

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
    start_full_tunnel,
    WindowsTunnelResult,
)


class TestNonAdminProductAttach(unittest.TestCase):
    def test_policy_no_run_as_admin_required(self):
        self.assertTrue(non_admin_connect_allowed())
        self.assertFalse(product_connect_requires_admin())
        self.assertFalse(auto_connect_on_launch_enabled())

    def test_start_full_tunnel_queue_fallback_when_wintun_fails(self):
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
                "104.156.224.47",
                prefer_system_capture=True,
            )

        self.assertTrue(res.ok, res.message)
        self.assertFalse(res.routes_applied)
        self.assertTrue(product_tunnel_attach_active(res))
        self.assertIn("queue", res.message.lower() or "queue" in (qtun.mode or ""))
        self.assertNotIn("Run as Administrator", res.message)

    def test_product_attach_active_requires_dataplane(self):
        plane = mock.Mock()
        plane.is_running.return_value = True
        self.assertFalse(product_tunnel_attach_active(None))
        self.assertFalse(
            product_tunnel_attach_active(
                WindowsTunnelResult(False, "x", [], dataplane=plane)
            )
        )
        self.assertTrue(
            product_tunnel_attach_active(
                WindowsTunnelResult(True, "up", [], dataplane=plane)
            )
        )

    def test_app_connect_uses_attach_active_not_admin_gate(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("product_tunnel_attach_active", src)
        self.assertIn("non_admin_connect_allowed", src)
        self.assertNotIn("_auto_connect", src)
        # Elevation may exist but must not be required for Connect success
        self.assertIn("Connect still works without Administrator", src)
        conn = src[src.index("def _start_connect") : src.index("def _start_disconnect")]
        self.assertIn("start_full_tunnel", conn)
        self.assertIn("product_tunnel_attach_active", conn)
        self.assertNotIn("Requesting UAC", conn)

    def test_tunnel_source_always_queue_fallback(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        self.assertIn("force_queue=True", src)
        self.assertIn("using in-process dataplane", src)
        # Must not hard-return Administrator-only without trying queue
        # (old fail-closed string)
        self.assertNotIn(
            "Run as Administrator; wintun.dll must load.",
            src,
        )


if __name__ == "__main__":
    unittest.main()
