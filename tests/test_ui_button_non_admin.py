"""Connect button always visible; residual Connect elevates; diagnostic queue path exists."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import build_full_tunnel_plan  # noqa: E402
from client.ui_theme import connect_button_label  # noqa: E402
from client.windows.app import (  # noqa: E402
    TunnelClientApp,
    layout_pack_bottom_controls_first,
    non_admin_connect_allowed,
    product_connect_requires_admin,
)
from client.windows.tunnel_win import start_full_tunnel  # noqa: E402


class TestButtonLayout(unittest.TestCase):
    def test_layout_policy_bottom_first(self):
        self.assertTrue(layout_pack_bottom_controls_first())

    def test_source_packs_bottom_before_log(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        bot = src.index("self.bottom.pack(side=tk.BOTTOM")
        log = src.index("self.log_shell.pack")
        self.assertLess(bot, log, "bottom Connect bar must pack before expanding log")
        self.assertIn("connect_btn", src)
        self.assertIn("connect_button_label", src)

    def test_tk_construct_connect_button_visible(self):
        import tkinter as tk

        try:
            app = TunnelClientApp()
        except tk.TclError as e:
            self.skipTest(f"no display: {e}")
            return

        try:
            app.root.update_idletasks()
            app.root.update()
            text = app.connect_button_text()
            self.assertEqual(text, connect_button_label(False))
            self.assertEqual(text, "Connect")
            self.assertTrue(app.connect_btn.winfo_exists())
            info = app.connect_btn.pack_info()
            self.assertTrue(info)
            binfo = app.bottom.pack_info()
            self.assertEqual(binfo.get("side"), "bottom")
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass


class TestNonAdminConnect(unittest.TestCase):
    def test_non_admin_ui_allowed_residual_requires_admin(self):
        self.assertTrue(non_admin_connect_allowed())
        self.assertTrue(product_connect_requires_admin())

    def test_start_full_tunnel_queue_without_require_system_capture(self):
        """Diagnostic path: queue fallback when residual capture not required."""
        client = mock.Mock()
        client.session = mock.Mock()
        client._sock = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.9")

        with mock.patch(
            "client.windows.tunnel_win.create_windows_tun"
        ) as create_tun, mock.patch(
            "client.windows.tunnel_win.is_admin", return_value=False
        ), mock.patch(
            "client.windows.tunnel_win.system_capture_ready", return_value=False
        ), mock.patch(
            "client.windows.tunnel_win.dataplane_enabled", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.RptDataPlane"
        ) as Plane, mock.patch(
            "client.windows.tunnel_win.time.sleep"
        ):
            qtun = mock.Mock()
            qtun.name = "RPT"
            qtun.mode = "queue"
            qtun.configure_address.return_value = []
            create_tun.side_effect = [RuntimeError("Wintun needs admin"), qtun]
            plane = mock.Mock()
            plane.is_running.return_value = True
            Plane.return_value = plane

            res = start_full_tunnel(
                client,
                plan,
                "82.221.101.241",
                prefer_system_capture=True,
                require_system_capture=False,
            )
            self.assertTrue(res.ok, res.message)
            self.assertFalse(res.routes_applied)
            plane.start.assert_called_once()

    def test_product_require_system_capture_blocks_non_admin(self):
        client = mock.Mock()
        client.session = mock.Mock()
        plan = build_full_tunnel_plan("10.88.0.9")
        with mock.patch("client.windows.tunnel_win.is_admin", return_value=False):
            res = start_full_tunnel(
                client,
                plan,
                "82.221.101.241",
                require_system_capture=True,
            )
        self.assertFalse(res.ok)
        self.assertIn("Administrator", res.message)

    def test_main_elevates_for_residual(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("elevate_if_needed", src)
        self.assertIn("require_system_capture=True", src)
        self.assertIn("TunnelClientApp()", src)


class TestDisconnectStillStops(unittest.TestCase):
    def test_disconnect_full_tunnel_wired(self):
        from client.windows import app as win_app

        client = mock.Mock()
        tunnel = mock.Mock()
        with mock.patch.object(win_app, "stop_full_tunnel") as stop:
            win_app.disconnect_full_tunnel(tunnel, client)
            stop.assert_called_once()
            self.assertEqual(stop.call_args[0][:2], (tunnel, client))


if __name__ == "__main__":
    unittest.main()
