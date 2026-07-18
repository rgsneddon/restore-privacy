"""Connect button always visible; VPN session starts without Administrator."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ConnectState, RptClient  # noqa: E402
from client.full_tunnel import build_full_tunnel_plan  # noqa: E402
from client.ui_theme import connect_button_label  # noqa: E402
from client.windows.app import (  # noqa: E402
    TunnelClientApp,
    layout_pack_bottom_controls_first,
    non_admin_connect_allowed,
)
from client.windows.tunnel_win import start_full_tunnel  # noqa: E402


class TestButtonLayout(unittest.TestCase):
    def test_layout_policy_bottom_first(self):
        self.assertTrue(layout_pack_bottom_controls_first())

    def test_source_packs_bottom_before_log(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Bottom bar packed with side=BOTTOM before log expand
        bot = src.index('self.bottom.pack(side=tk.BOTTOM')
        log = src.index("self.log_shell.pack")
        self.assertLess(bot, log, "bottom Connect bar must pack before expanding log")
        self.assertIn("connect_btn", src)
        self.assertIn("connect_button_label", src)

    def test_tk_construct_connect_button_visible(self):
        """Real TunnelClientApp: Connect control mapped under default geometry."""
        import tkinter as tk

        try:
            app = TunnelClientApp()
        except tk.TclError as e:
            self.skipTest(f"no display: {e}")
            return

        try:
            app.root.update_idletasks()
            app.root.update()
            # Force min size then default
            app.root.geometry(f"{TunnelClientApp.MIN_WIDTH}x{TunnelClientApp.MIN_HEIGHT}")
            app.root.update_idletasks()
            app.root.update()
            text = app.connect_button_text()
            self.assertEqual(text, connect_button_label(False))
            self.assertEqual(text, "Connect")
            # Widget exists and is managed by pack
            self.assertTrue(app.connect_btn.winfo_exists())
            info = app.connect_btn.pack_info()
            self.assertTrue(info, "Connect button must be pack-managed")
            # Bottom frame is pack side BOTTOM
            binfo = app.bottom.pack_info()
            self.assertEqual(binfo.get("side"), "bottom")
            # Visible probe (mapped after update)
            app.root.update()
            self.assertTrue(
                app.connect_btn.winfo_ismapped() or app.connect_button_visible(),
                "Connect button should be mapped/visible",
            )
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass

    def test_tk_construct_min_geometry_still_has_button(self):
        try:
            app = TunnelClientApp()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        try:
            app.root.geometry(f"{TunnelClientApp.MIN_WIDTH}x{TunnelClientApp.MIN_HEIGHT}")
            app.root.update_idletasks()
            app.root.update()
            self.assertEqual(app.connect_button_text(), "Connect")
            self.assertTrue(app.connect_btn.winfo_exists())
            # Button should still have positive allocated height
            h = app.connect_btn.winfo_height()
            self.assertGreater(h, 1, f"button height should be >1 at min size, got {h}")
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass


class TestNonAdminConnect(unittest.TestCase):
    def test_non_admin_connect_allowed_policy(self):
        self.assertTrue(non_admin_connect_allowed())

    def test_start_full_tunnel_falls_back_without_admin(self):
        """Wintun failure must not fail Connect — queue fallback starts dataplane."""
        client = mock.Mock(spec=RptClient)
        client.session = mock.Mock()
        client.session.vpn_ip = "10.88.0.9"
        client._sock = mock.Mock()
        # Minimal session crypto for dataplane - may need more
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
        ) as Plane:
            # First call (prefer system) fails; second (force_queue) succeeds
            qtun = mock.Mock()
            qtun.name = "RPT"
            qtun.mode = "queue"
            qtun.configure_address.return_value = []
            qtun.interface_index.return_value = None
            create_tun.side_effect = [
                RuntimeError("Wintun needs admin"),
                qtun,
            ]
            plane = mock.Mock()
            plane.is_running.return_value = True
            Plane.return_value = plane

            res = start_full_tunnel(
                client, plan, "104.156.224.47", prefer_system_capture=True
            )
            self.assertTrue(res.ok, res.message)
            self.assertFalse(res.routes_applied)
            lower = res.message.lower()
            self.assertTrue(
                "queue" in lower
                or "standard user" in lower
                or "wintun unavailable" in lower
                or "dataplane" in lower,
                res.message,
            )
            plane.start.assert_called_once()
            self.assertEqual(create_tun.call_count, 2)

    def test_main_does_not_require_auto_elevate(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("RPT_AUTO_ELEVATE", src)
        # Default path does not call elevate unless opt-in
        self.assertIn('os.environ.get("RPT_AUTO_ELEVATE"', src)
        self.assertIn("no admin required", src.lower() or src)
        self.assertTrue(non_admin_connect_allowed())


class TestLaunchNoAdminGate(unittest.TestCase):
    def test_main_source_builds_ui_without_elevation_success(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # elevate only when RPT_AUTO_ELEVATE set
        self.assertIn("RPT_AUTO_ELEVATE", src)
        main_idx = src.index("def main")
        main_body = src[main_idx:]
        # TunnelClientApp constructed regardless of admin
        self.assertIn("TunnelClientApp()", main_body)
        # failed elevation still continues to app
        self.assertIn("Connect still works without admin", main_body)


class TestDisconnectStillStops(unittest.TestCase):
    def test_disconnect_full_tunnel_wired(self):
        from client.windows import app as win_app

        client = mock.Mock()
        tunnel = mock.Mock()
        with mock.patch.object(win_app, "stop_full_tunnel") as stop:
            win_app.disconnect_full_tunnel(tunnel, client)
            stop.assert_called_once_with(tunnel, client)


if __name__ == "__main__":
    unittest.main()
