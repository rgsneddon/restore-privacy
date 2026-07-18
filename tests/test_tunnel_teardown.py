"""Full tunnel teardown on app close — Windows routes/stop + Android disconnect wiring.

Tests drive the shipped teardown helpers and source control-flow (not reimplementations).
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ConnectState, RptClient  # noqa: E402
from client.full_tunnel import (  # noqa: E402
    build_full_tunnel_plan,
    windows_route_delete_commands,
)
from client.windows.tunnel_win import (  # noqa: E402
    WindowsTunnelResult,
    stop_full_tunnel,
)


class TestWindowsRouteDeleteCommands(unittest.TestCase):
    """Shipped delete-command builder must reverse full-tunnel install."""

    def test_delete_covers_dual_slash1_and_server_pin(self):
        plan = build_full_tunnel_plan("10.88.0.9", tunnel_iface="RPT")
        server = "104.156.224.47"
        cmds = windows_route_delete_commands(plan, server, if_index=12)
        joined = "\n".join(cmds)
        self.assertIn(f"route delete {server} mask 255.255.255.255", joined)
        self.assertIn("route delete 0.0.0.0 mask 128.0.0.0", joined)
        self.assertIn("route delete 128.0.0.0 mask 128.0.0.0", joined)
        # No leftover add of catch-alls in teardown list
        self.assertNotIn("route add", joined)

    def test_delete_idempotent_shape(self):
        plan = build_full_tunnel_plan("10.88.0.2")
        a = windows_route_delete_commands(plan, "1.2.3.4", if_index=1)
        b = windows_route_delete_commands(plan, "1.2.3.4", if_index=None)
        # Same essential deletes regardless of if_index (routes are not IF-scoped on delete)
        self.assertEqual(a, b)


class TestStopFullTunnel(unittest.TestCase):
    """stop_full_tunnel: routes first, then dataplane, TUN, session — idempotent."""

    def test_stop_with_no_tunnel_is_safe(self):
        client = RptClient()
        # Never connected
        applied = stop_full_tunnel(None, client)
        self.assertIsInstance(applied, list)
        self.assertEqual(client.state, ConnectState.DISCONNECTED)

    def test_stop_twice_is_safe(self):
        client = RptClient()
        stop_full_tunnel(None, client)
        stop_full_tunnel(None, client)
        self.assertEqual(client.state, ConnectState.DISCONNECTED)

    def test_stop_calls_route_rollback_dataplane_tun_and_disconnect(self):
        plan = build_full_tunnel_plan("10.88.0.5", tunnel_iface="RPT")
        server = "104.156.224.47"
        plane = mock.Mock()
        tun = mock.Mock()
        client = mock.Mock(spec=RptClient)
        result = WindowsTunnelResult(
            ok=True,
            message="up",
            applied_commands=[],
            tun=tun,
            dataplane=plane,
            routes_applied=True,
            plan=plan,
            server_host=server,
            if_index=17,
        )
        with mock.patch(
            "client.windows.tunnel_win.rollback_full_tunnel_routes",
            return_value=["route delete 0.0.0.0 mask 128.0.0.0"],
        ) as rb:
            applied = stop_full_tunnel(result, client)
        rb.assert_called_once()
        args, _kwargs = rb.call_args
        self.assertEqual(args[0], plan)
        self.assertEqual(args[1], server)
        self.assertEqual(args[2], 17)
        plane.stop.assert_called_once()
        tun.close.assert_called_once()
        client.disconnect.assert_called_once()
        self.assertTrue(any("128.0.0.0" in c for c in applied))
        self.assertFalse(result.routes_applied)
        self.assertIsNone(result.dataplane)
        self.assertIsNone(result.tun)

    def test_stop_without_routes_still_stops_dataplane_and_session(self):
        plane = mock.Mock()
        tun = mock.Mock()
        client = mock.Mock(spec=RptClient)
        result = WindowsTunnelResult(
            ok=True,
            message="session only",
            applied_commands=[],
            tun=tun,
            dataplane=plane,
            routes_applied=False,
            plan=None,
            server_host=None,
        )
        with mock.patch(
            "client.windows.tunnel_win.rollback_full_tunnel_routes"
        ) as rb:
            stop_full_tunnel(result, client)
        rb.assert_not_called()
        plane.stop.assert_called_once()
        tun.close.assert_called_once()
        client.disconnect.assert_called_once()

    def test_stop_swallows_component_errors(self):
        plane = mock.Mock()
        plane.stop.side_effect = RuntimeError("plane boom")
        tun = mock.Mock()
        tun.close.side_effect = OSError("tun boom")
        client = mock.Mock(spec=RptClient)
        client.disconnect.side_effect = RuntimeError("disc boom")
        plan = build_full_tunnel_plan("10.88.0.2")
        result = WindowsTunnelResult(
            ok=True,
            message="up",
            applied_commands=[],
            tun=tun,
            dataplane=plane,
            routes_applied=True,
            plan=plan,
            server_host="1.1.1.1",
            if_index=3,
        )
        with mock.patch(
            "client.windows.tunnel_win.rollback_full_tunnel_routes",
            side_effect=OSError("route boom"),
        ):
            # Must not raise
            stop_full_tunnel(result, client)
        plane.stop.assert_called_once()
        tun.close.assert_called_once()
        client.disconnect.assert_called_once()


class TestWindowsAppCloseHook(unittest.TestCase):
    """Close is UI-only; Disconnect (not close) runs full teardown."""

    def test_app_source_close_ui_only_disconnect_tears_down(self):
        app_path = ROOT / "client" / "windows" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        self.assertIn("stop_full_tunnel", src)
        self.assertIn("WM_DELETE_WINDOW", src)
        self.assertIn("_on_close_ui_only", src)
        self.assertIn("disconnect_full_tunnel", src)
        self.assertIn('protocol("WM_DELETE_WINDOW"', src)
        # Close must not call stop/teardown
        on_close = src[src.index("def _on_close_ui_only") : src.index("def run")]
        self.assertNotIn("stop_full_tunnel", on_close)
        self.assertNotIn("disconnect_full_tunnel", on_close)
        self.assertIn("destroy", on_close)
        # run() has no finally teardown
        run_body = src[src.index("def run") : src.index("def run") + 180]
        self.assertNotIn("stop_full_tunnel", run_body)

    def test_disconnect_helper_calls_shipped_stop(self):
        """AST: disconnect_full_tunnel body references stop_full_tunnel."""
        app_path = ROOT / "client" / "windows" / "app.py"
        tree = ast.parse(app_path.read_text(encoding="utf-8"))
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "disconnect_full_tunnel":
                body = ast.dump(node)
                self.assertIn("stop_full_tunnel", body)
                found = True
        self.assertTrue(found, "disconnect_full_tunnel not found")


class TestAndroidTeardownWiring(unittest.TestCase):
    """Android disconnect/close must stop TUN service and not sticky-restart after stop."""

    KT = (
        ROOT
        / "client_app"
        / "android"
        / "app"
        / "src"
        / "main"
        / "kotlin"
        / "com"
        / "restoreprivacy"
        / "restore_privacy_client"
    )
    LIB = ROOT / "client_app" / "lib"

    def test_service_disconnect_closes_tun_and_not_sticky(self):
        svc = (self.KT / "RptVpnService.kt").read_text(encoding="utf-8")
        self.assertIn("ACTION_DISCONNECT", svc)
        self.assertIn("fun stopTunnel", svc)
        # TUN close on stop path (pfd local or tun field)
        self.assertTrue(
            "pfd?.close" in svc or "tun?.close" in svc,
            "stopTunnel must close ParcelFileDescriptor",
        )
        self.assertIn("stopSelf", svc)
        self.assertIn("STOP_FOREGROUND_REMOVE", svc)
        # Intentional disconnect returns NOT_STICKY
        self.assertIn("START_NOT_STICKY", svc)
        disc_idx = svc.index("ACTION_DISCONNECT")
        sticky_region = svc[disc_idx : disc_idx + 400]
        self.assertIn("START_NOT_STICKY", sticky_region)
        self.assertIn("userStopped", svc)
        # onDestroy + onRevoke tear down
        self.assertIn("override fun onDestroy", svc)
        self.assertIn("override fun onRevoke", svc)
        destroy = svc[svc.index("override fun onDestroy") :]
        self.assertIn("stopTunnel", destroy.split("override fun")[0] if False else destroy[:300])
        revoke = svc[svc.index("override fun onRevoke") : svc.index("override fun onRevoke") + 250]
        self.assertIn("stopTunnel", revoke)

    def test_main_activity_disconnect_sends_action_and_on_destroy(self):
        act = (self.KT / "MainActivity.kt").read_text(encoding="utf-8")
        self.assertIn("ACTION_DISCONNECT", act)
        self.assertIn("sendDisconnect", act)
        self.assertIn('"disconnect"', act)
        # disconnect channel uses sendDisconnect / ACTION_DISCONNECT
        disc_block = act[act.index('"disconnect"') : act.index('"disconnect"') + 350]
        self.assertIn("sendDisconnect", disc_block)
        self.assertIn("override fun onDestroy", act)
        on_destroy = act[act.index("override fun onDestroy") : act.index("override fun onDestroy") + 200]
        self.assertIn("sendDisconnect", on_destroy)

    def test_flutter_dispose_and_detached_call_disconnect(self):
        main = (self.LIB / "main.dart").read_text(encoding="utf-8")
        self.assertIn("WidgetsBindingObserver", main)
        self.assertIn("shouldStopTunnelOnAppLifecycle", main)
        self.assertIn("_teardownVpn", main)
        self.assertIn("disconnect()", main)
        # dispose tears down
        disp = main[main.index("void dispose") : main.index("void dispose") + 280]
        self.assertIn("_teardownVpn", disp)
        self.assertIn("removeObserver", disp)
        # Lifecycle uses pure helper (detached only — not pause/background)
        life = main[
            main.index("didChangeAppLifecycleState") : main.index(
                "didChangeAppLifecycleState"
            )
            + 350
        ]
        self.assertIn("shouldStopTunnelOnAppLifecycle", life)
        self.assertIn("_teardownVpn", life)
        # Not required on pause (product choice)
        self.assertNotIn("AppLifecycleState.paused", main)

    def test_vpn_controller_disconnect_invokes_channel(self):
        ctrl = (self.LIB / "vpn_controller.dart").read_text(encoding="utf-8")
        self.assertIn("Future<void> disconnect()", ctrl)
        self.assertIn("invokeMethod", ctrl)
        self.assertIn("'disconnect'", ctrl)


if __name__ == "__main__":
    unittest.main()
