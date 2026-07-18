"""Manual Connect/Disconnect UI: no auto-connect, no close teardown, sleek status, upgrade."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.ui_theme import (  # noqa: E402
    CHROME_BG,
    CORNER_RADIUS,
    PALETTE_SOURCE_URL,
    PRIMARY,
    connect_button_label,
    plain_tunnel_status,
    upgrade_available,
    upgrade_banner_text,
    version_is_behind,
)
from client.windows.app import (  # noqa: E402
    TunnelClientApp,
    auto_connect_on_launch_enabled,
    close_disconnects_tunnel,
    disconnect_full_tunnel,
)


class TestManualControlPolicy(unittest.TestCase):
    def test_no_auto_connect_policy(self):
        self.assertFalse(auto_connect_on_launch_enabled())

    def test_close_does_not_disconnect_policy(self):
        self.assertFalse(close_disconnects_tunnel())

    def test_app_source_no_auto_connect(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_auto_connect", src)
        self.assertNotIn("auto_connect_on_launch()", src)
        self.assertIn("_on_close_ui_only", src)
        self.assertIn("_start_connect", src)
        self.assertIn("_start_disconnect", src)
        # main must not schedule connect
        main = src[src.index("def main") :]
        self.assertNotIn("after(200", main)
        self.assertNotIn("_start_connect)", main.replace("app._start_connect", ""))
        self.assertIn("Never schedule auto-connect", main)

    def test_close_path_no_teardown(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        close = src[src.index("def _on_close_ui_only") : src.index("def run")]
        self.assertNotIn("stop_full_tunnel", close)
        self.assertNotIn("disconnect_full_tunnel", close)
        self.assertIn("destroy", close)
        run = src[src.index("def run") : src.index("def run") + 200]
        self.assertNotIn("stop_full_tunnel", run)
        self.assertNotIn("finally:", run)

    def test_disconnect_calls_stop_helper(self):
        client = mock.Mock()
        tunnel = mock.Mock()
        with mock.patch("client.windows.app.stop_full_tunnel") as stop:
            disconnect_full_tunnel(tunnel, client)
            stop.assert_called_once_with(tunnel, client)

    def test_disconnect_handler_wired_in_source(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        disc = src[src.index("def _start_disconnect") : src.index("def _open_upgrade")]
        self.assertIn("disconnect_full_tunnel", disc)
        self.assertIn('self._set_status("disconnecting")', disc)
        self.assertIn("Disconnecting…", src)  # button busy label in _apply_control

    def test_connect_handler_starts_tunnel(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        conn = src[src.index("def _start_connect") : src.index("def _start_disconnect")]
        self.assertIn("self.client.connect", conn)
        self.assertIn("start_full_tunnel", conn)


class TestThemeAndStatus(unittest.TestCase):
    def test_palette_from_contact_page_source(self):
        self.assertIn("restorebritain.org.uk/contact", PALETTE_SOURCE_URL)
        self.assertTrue(PRIMARY.startswith("#"))
        self.assertTrue(CHROME_BG.startswith("#"))
        self.assertGreaterEqual(CORNER_RADIUS, 8)

    def test_plain_status_wording(self):
        self.assertEqual(plain_tunnel_status("disconnected"), "Disconnected")
        self.assertIn("Connecting", plain_tunnel_status("connecting"))
        self.assertIn("Connected", plain_tunnel_status("connected", vpn_ip="10.88.0.2"))
        self.assertIn("10.88.0.2", plain_tunnel_status("connected", vpn_ip="10.88.0.2"))
        err = plain_tunnel_status("error", detail="timeout talking to node")
        self.assertIn("Could not connect", err)
        # Must not dump route tables as primary
        self.assertNotIn("route add", plain_tunnel_status("connected"))
        self.assertNotIn("mask 128", plain_tunnel_status("disconnected"))

    def test_button_labels(self):
        self.assertEqual(connect_button_label(False), "Connect")
        self.assertEqual(connect_button_label(True), "Disconnect")

    def test_app_uses_theme_and_status_panel(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("plain_tunnel_status", src)
        self.assertIn("status_card", src)
        self.assertIn("CHROME_BG", src)
        self.assertIn("CORNER_RADIUS", (ROOT / "client" / "ui_theme.py").read_text(encoding="utf-8"))


class TestUpgradeOption(unittest.TestCase):
    def test_version_is_behind(self):
        self.assertTrue(version_is_behind("0.1.2", "0.1.3"))
        self.assertFalse(version_is_behind("0.1.3", "0.1.3"))
        self.assertFalse(version_is_behind("0.1.4", "0.1.3"))
        self.assertTrue(version_is_behind("0.0.8", "0.1.3"))

    def test_upgrade_available_helpers(self):
        self.assertTrue(upgrade_available("0.1.0", "0.1.3"))
        self.assertFalse(upgrade_available("0.1.3", "0.1.3"))
        msg = upgrade_banner_text("0.1.0", "0.1.3")
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("0.1.0", msg)
        self.assertIn("0.1.3", msg)
        self.assertIsNone(upgrade_banner_text("0.1.3", "0.1.3"))

    def test_app_wires_upgrade_ui(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("upgrade_banner_text", src)
        self.assertIn("upgrade_download_url", src)
        self.assertIn("_open_upgrade", src)
        self.assertIn("Get update", src)

    def test_catalog_version_is_concrete(self):
        from status_page.downloads import RELEASE_VERSION

        self.assertRegex(RELEASE_VERSION, r"^\d+\.\d+")


class TestTkConstructIdle(unittest.TestCase):
    def test_window_opens_disconnected_with_connect(self):
        try:
            app = TunnelClientApp()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        try:
            app.root.update_idletasks()
            app.root.update()
            self.assertEqual(app.connect_button_text(), "Connect")
            self.assertFalse(app._connected)
            self.assertIn("Disconnected", app.status_var.get())
            # No auto-connect scheduled as attribute
            self.assertFalse(auto_connect_on_launch_enabled())
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
