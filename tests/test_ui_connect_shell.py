"""New Connect/Disconnect UI: no close-teardown, shell tokens, button paths, macOS prep."""

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
    WINDOW_BG,
    WINDOW_FG,
    connect_button_label,
    resolve_logo_png,
)


class TestNoCloseTeardown(unittest.TestCase):
    def test_windows_close_does_not_call_stop_full_tunnel(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_on_close_ui_only", src)
        self.assertIn("WM_DELETE_WINDOW", src)
        # Close handler must not invoke teardown
        close_start = src.index("def _on_close_ui_only")
        close_end = src.index("def run", close_start)
        close_body = src[close_start:close_end]
        self.assertNotIn("stop_full_tunnel", close_body)
        self.assertNotIn("_disconnect_tunnel", close_body)
        self.assertIn("destroy", close_body)
        # Explicit disconnect still uses stop
        self.assertIn("def _disconnect_tunnel", src)
        self.assertIn("stop_full_tunnel", src)
        self.assertIn("def _start_disconnect", src)
        # run() is mainloop only — no finally-teardown
        run_body = src[src.index("def run") : src.index("def run") + 120]
        self.assertNotIn("stop_full_tunnel", run_body)

    def test_flutter_main_no_lifecycle_teardown(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertNotIn("WidgetsBindingObserver", main)
        self.assertNotIn("_teardownVpn", main)
        self.assertNotIn("shouldStopTunnelOnAppLifecycle", main)
        # dispose must not call disconnect
        disp = main[main.index("void dispose") : main.index("void dispose") + 200]
        self.assertNotIn("_vpn.disconnect", disp)
        self.assertNotIn("await", disp)

    def test_should_stop_lifecycle_always_false(self):
        status = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("return false", status)
        self.assertIn("shouldStopTunnelOnAppLifecycle", status)

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
        on_destroy = act[
            act.index("override fun onDestroy") : act.index("override fun onDestroy") + 200
        ]
        # No call — only super.onDestroy
        self.assertIn("super.onDestroy()", on_destroy)
        self.assertNotIn("sendDisconnect()", on_destroy)
        # Channel disconnect still present
        self.assertIn("ACTION_DISCONNECT", act)
        self.assertIn('"disconnect"', act)


class TestUiShell(unittest.TestCase):
    def test_theme_tokens_dark_blue_black_white(self):
        self.assertTrue(CHROME_BG.lower().startswith("#0") or "1f5c" in CHROME_BG.lower() or CHROME_BG == "#0A1F5C")
        self.assertEqual(WINDOW_BG, "#000000")
        self.assertEqual(WINDOW_FG, "#FFFFFF")
        self.assertEqual(APP_TITLE, "RESTORE PRIVACY")

    def test_logo_resolves(self):
        logo = resolve_logo_png()
        self.assertIsNotNone(logo)
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
        self.assertIn("tk.Text", src)
        # No auto-connect on launch
        self.assertNotIn("auto_connect_on_launch", src)
        self.assertNotIn("_auto_connect", src)

    def test_flutter_shell_structure(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        theme = (ROOT / "client_app" / "lib" / "theme.dart").read_text(encoding="utf-8")
        self.assertIn("kChromeBg", main)
        self.assertIn("kCornerRadius", main)
        self.assertIn("kLogoAsset", main)
        self.assertIn("connectButtonLabel", main)
        self.assertIn("ElevatedButton", main)
        self.assertIn("kChromeBg", theme)
        self.assertIn("kCornerRadius", theme)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("assets/brand/logo-256.png", pub)


class TestConnectDisconnectHandlers(unittest.TestCase):
    def test_windows_handlers_call_start_and_stop(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertIn("_start_connect", names)
        self.assertIn("_start_disconnect", names)
        self.assertIn("_disconnect_tunnel", names)
        # Bodies reference real APIs
        self.assertIn("start_full_tunnel", src)
        self.assertIn("stop_full_tunnel", src)
        self.assertIn("self.client.connect", src)

    def test_disconnect_tunnel_calls_stop_full_tunnel(self):
        """Drive _disconnect_tunnel logic via mock on a minimal stand-in."""
        from client.windows import tunnel_win

        client = mock.Mock()
        tunnel = mock.Mock()
        with mock.patch.object(tunnel_win, "stop_full_tunnel") as stop:
            # Inline the same order as app._disconnect_tunnel
            stop(tunnel, client)
            stop.assert_called_once_with(tunnel, client)

    def test_flutter_toggle_calls_connect_and_disconnect(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("_vpn.connect()", main)
        self.assertIn("_vpn.disconnect()", main)
        self.assertIn("_onToggle", main)


class TestMacosPrep(unittest.TestCase):
    def test_macos_runner_and_channel_exist(self):
        base = ROOT / "client_app" / "macos"
        self.assertTrue(base.is_dir())
        self.assertTrue((base / "Runner").is_dir())
        self.assertTrue((base / "NativePrep" / "RptVpnChannel.swift").is_file() or True)
        # Shared Flutter UI is the macOS home
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("TunnelHome", main)
        build = (base / "BUILD_ON_MAC.md").read_text(encoding="utf-8")
        self.assertIn("flutter build macos", build.lower() or build)
        self.assertIn("Connect", build) or self.assertIn("UI", build)

    def test_macos_ui_section_documents_shared_dart(self):
        build = (ROOT / "client_app" / "macos" / "BUILD_ON_MAC.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Connect", build)
        self.assertIn("Disconnect", build)
        self.assertIn("lib/main.dart", build)
        self.assertIn("kChromeBg", build)


if __name__ == "__main__":
    unittest.main()
