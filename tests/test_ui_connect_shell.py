"""Connect/Disconnect UI shell: no close-teardown, logo, handlers (v0.1.4 product)."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.ui_theme import (  # noqa: E402
    APP_TITLE,
    CHROME_BG,
    PRIMARY,
    connect_button_label,
    resolve_logo_png,
)


class TestNoCloseTeardown(unittest.TestCase):
    def test_windows_close_does_not_call_stop_full_tunnel(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_on_close_ui_only", src)
        self.assertIn("WM_DELETE_WINDOW", src)
        close_start = src.index("def _on_close_ui_only")
        close_end = src.index("def _quit_app", close_start)
        close_body = src[close_start:close_end]
        self.assertNotIn("stop_full_tunnel", close_body)
        self.assertNotIn("disconnect_full_tunnel", close_body)
        self.assertTrue("withdraw" in close_body or "iconify" in close_body)
        self.assertIn("def _disconnect_tunnel", src)
        self.assertIn("stop_full_tunnel", src)
        self.assertIn("def _start_disconnect", src)
        run_body = src[src.index("def run") : src.index("def run") + 200]
        self.assertNotIn("stop_full_tunnel", run_body)

    def test_flutter_main_no_lifecycle_teardown(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        # Lifecycle observer may rehydrate status only — must not stop tunnel
        self.assertNotIn("_teardownVpn", main)
        self.assertIn("shouldStopTunnelOnAppLifecycle", main)
        if "void dispose" in main:
            disp = main[main.index("void dispose") : main.index("void dispose") + 280]
            self.assertNotIn("_vpn.disconnect", disp)
            self.assertNotIn(".disconnect()", disp)

    def test_should_stop_lifecycle_always_false(self):
        status = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("shouldStopTunnelOnAppLifecycle", status)
        self.assertIn("return false", status)

    def test_android_ondestroy_does_not_send_disconnect(self):
        act = (
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
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("onDestroy", act)
        on_destroy = act[act.index("onDestroy") : act.index("onDestroy") + 280]
        self.assertIn("super.onDestroy()", on_destroy)
        self.assertNotIn("sendDisconnect()", on_destroy)


class TestUiShell(unittest.TestCase):
    def test_theme_tokens_product_chrome(self):
        # v0.1.4 uses restorebritain Cupertino palette (not pure black retro)
        self.assertTrue(CHROME_BG.startswith("#"))
        self.assertTrue(PRIMARY.startswith("#"))
        self.assertIn("Privacy", APP_TITLE)

    def test_logo_resolves(self):
        logo = resolve_logo_png()
        self.assertIsNotNone(logo)
        assert logo is not None
        self.assertTrue(logo.is_file())

    def test_connect_button_label_helper(self):
        self.assertEqual(connect_button_label(False), "Connect")
        self.assertEqual(connect_button_label(True), "Disconnect")

    def test_windows_app_has_shell_and_button(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("CHROME_BG", src)
        self.assertIn("connect_button_label", src)
        self.assertIn("_on_toggle_connect", src)
        self.assertIn("resolve_logo_png", src)
        self.assertIn("tk.Button", src)
        self.assertNotIn("_auto_connect", src)

    def test_flutter_shell_structure(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        theme = (ROOT / "client_app" / "lib" / "theme.dart").read_text(encoding="utf-8")
        self.assertIn("ElevatedButton", main)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertTrue(
            "assets/brand" in pub or "logo" in pub.lower(),
            "flutter assets should include brand logo",
        )
        self.assertTrue("kChromeBg" in theme or "Color" in theme)


class TestConnectDisconnectHandlers(unittest.TestCase):
    def test_windows_handlers_call_start_and_stop(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertIn("_start_connect", names)
        self.assertIn("_start_disconnect", names)
        self.assertIn("_disconnect_tunnel", names)
        self.assertIn("start_full_tunnel", src)
        self.assertIn("stop_full_tunnel", src)
        self.assertIn("self.client.connect", src)
        self.assertIn("require_system_capture=True", src)

    def test_disconnect_full_tunnel_calls_stop_full_tunnel(self):
        from client.windows import app as win_app

        client = mock.Mock()
        tunnel = mock.Mock()
        with mock.patch.object(win_app, "stop_full_tunnel") as stop:
            win_app.disconnect_full_tunnel(tunnel, client)
            stop.assert_called_once()
            self.assertEqual(stop.call_args[0][:2], (tunnel, client))

        with mock.patch.object(
            win_app, "stop_full_tunnel", side_effect=RuntimeError("x")
        ):
            win_app.disconnect_full_tunnel(tunnel, client)
            client.disconnect.assert_called()

    def test_app_disconnect_tunnel_method_uses_shipped_helper(self):
        from client.windows import app as win_app

        with mock.patch.object(win_app, "disconnect_full_tunnel") as disc:
            obj = object.__new__(win_app.TunnelClientApp)
            obj._tunnel = mock.Mock(name="tunnel")
            obj.client = mock.Mock(name="client")
            win_app.TunnelClientApp._disconnect_tunnel(obj)
            self.assertIsNone(obj._tunnel)
            disc.assert_called_once()


class TestMacosPrep(unittest.TestCase):
    def test_macos_runner_and_channel_exist(self):
        base = ROOT / "client_app" / "macos"
        self.assertTrue(base.is_dir())
        self.assertTrue((base / "Runner").is_dir())
        self.assertTrue((base / "NativePrep" / "RptVpnChannel.swift").is_file())
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertTrue("TunnelHome" in main or "Connect" in main)


if __name__ == "__main__":
    unittest.main()
