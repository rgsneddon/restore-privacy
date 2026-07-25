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
        # Default settings: autoconnect off (opt-in via Settings)
        self.assertFalse(auto_connect_on_launch_enabled())

    def test_close_does_not_disconnect_policy(self):
        self.assertFalse(close_disconnects_tunnel())

    def test_app_source_manual_default_optional_autoconnect(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("def _auto_connect", src)
        self.assertIn("_on_close_ui_only", src)
        self.assertIn("_start_connect", src)
        self.assertIn("_start_disconnect", src)
        main = src[src.index("def main") :]
        self.assertNotIn("after(200", main)
        self.assertIn("resume_after_elevate", main)
        self.assertIn("_resume_user_connect", main)
        self.assertIn("should_autoconnect_on_launch", main)
        self.assertIn("_settings_autoconnect", main)

    def test_close_path_no_teardown(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Close hides (iconify/withdraw) — does not destroy process or stop tunnel
        close = src[src.index("def _on_close_ui_only") : src.index("def _quit_app")]
        self.assertNotIn("stop_full_tunnel", close)
        self.assertNotIn("disconnect_full_tunnel", close)
        self.assertTrue("iconify" in close or "withdraw" in close)
        self.assertNotIn("self.root.destroy()", close)
        # Explicit Quit stops tunnel then exits
        quit_body = src[src.index("def _quit_app") : src.index("def run")]
        self.assertIn("disconnect_full_tunnel", quit_body)
        self.assertIn("destroy", quit_body)
        run = src[src.index("def run") : src.index("def run") + 220]
        self.assertNotIn("stop_full_tunnel", run)
        self.assertNotIn("finally:", run)

    def test_main_wires_elevation_and_optional_settings_autoconnect(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        main = src[src.index("def main") :]
        self.assertIn("elevate_if_needed", main)
        self.assertIn("should_exit_after_elevation", main)
        self.assertIn("resume_after_elevate", main)
        self.assertIn("_resume_user_connect", main)
        self.assertIn("should_autoconnect_on_launch", main)

    def test_disconnect_calls_stop_helper(self):
        client = mock.Mock()
        tunnel = mock.Mock()
        with mock.patch("client.windows.app.stop_full_tunnel") as stop:
            disconnect_full_tunnel(tunnel, client)
            stop.assert_called_once()
            self.assertEqual(stop.call_args[0][:2], (tunnel, client))

    def test_disconnect_handler_wired_in_source(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        disc = src[src.index("def _start_disconnect") : src.index("def _open_upgrade")]
        self.assertTrue(
            "disconnect_full_tunnel" in disc or "_disconnect_tunnel" in disc
        )
        self.assertIn("def _disconnect_tunnel", src)
        self.assertIn("disconnect_full_tunnel", src)
        self.assertIn('self._set_status("disconnecting")', disc)
        self.assertIn("Disconnecting...", src)  # button busy label in _apply_control

    def test_connect_handler_starts_tunnel(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        conn = src[src.index("def _start_connect") : src.index("def _start_disconnect")]
        self.assertIn("self.client.connect", conn)
        self.assertIn("start_full_tunnel", conn)
        self.assertIn("require_system_capture=True", conn)
        self.assertIn("residual_ip_capture_active", conn)
        # Residual attach must not run on the Tk UI thread (Not Responding freeze)
        self.assertIn("threading.Thread", conn)
        self.assertIn("Attaching residual tunnel", conn)
        # start_full_tunnel must be in worker, not only inside a root.after done callback
        # that previously blocked the UI during Wintun/route install.
        attach_idx = conn.index("start_full_tunnel")
        # The note_session after() must appear before attach, and done after() after attach
        self.assertLess(conn.index("note_session"), attach_idx)
        self.assertGreater(conn.index("def done"), attach_idx)

    def test_linux_connect_tunnel_off_ui_thread(self):
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        conn = src[src.index("def _start_connect") : src.index("def _disconnect_tunnel")]
        self.assertIn("start_full_tunnel", conn)
        self.assertIn("threading.Thread", conn)
        self.assertIn("Attaching residual tunnel", conn)
        self.assertIn("assert_may_connect", conn)
        attach_idx = conn.index("start_full_tunnel")
        self.assertLess(conn.index("note_session"), attach_idx)
        self.assertGreater(conn.index("def done"), attach_idx)


class TestThemeAndStatus(unittest.TestCase):
    def test_palette_from_contact_page_source(self):
        self.assertIn("restorebritain.org.uk/contact", PALETTE_SOURCE_URL)
        self.assertTrue(PRIMARY.startswith("#"))
        self.assertTrue(CHROME_BG.startswith("#"))
        self.assertGreaterEqual(CORNER_RADIUS, 8)

    def test_plain_status_wording(self):
        from client.ui_theme import STATUS_ERROR, STATUS_ERROR_FG, STATUS_ERROR_LABEL

        self.assertEqual(plain_tunnel_status("disconnected"), "Disconnected")
        self.assertIn("Connecting", plain_tunnel_status("connecting"))
        self.assertIn("Connected", plain_tunnel_status("connected", vpn_ip="10.88.0.2"))
        self.assertIn("10.88.0.2", plain_tunnel_status("connected", vpn_ip="10.88.0.2"))
        residual_off = plain_tunnel_status(
            "connected", vpn_ip="10.88.0.2", residual_capture=False
        )
        self.assertIn("ISP", residual_off)
        self.assertNotIn("uses the VPN", residual_off)
        err = plain_tunnel_status("error", detail="timeout talking to node")
        self.assertIn("Could not connect", err)
        self.assertIn(STATUS_ERROR_LABEL, err)
        # Color constants must remain hex (not overwritten by message strings)
        self.assertTrue(STATUS_ERROR.startswith("#"), STATUS_ERROR)
        self.assertTrue(STATUS_ERROR_FG.startswith("#"), STATUS_ERROR_FG)
        self.assertEqual(STATUS_ERROR, STATUS_ERROR_FG)
        self.assertFalse(STATUS_ERROR_LABEL.startswith("#"))
        # Must not dump route tables as primary
        self.assertNotIn("route add", plain_tunnel_status("connected"))
        self.assertNotIn("mask 128", plain_tunnel_status("disconnected"))

    def test_set_status_error_uses_hex_fg(self):
        """Failed Connect must paint plain-language status without TclError on fg color."""
        try:
            app = TunnelClientApp()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        try:
            app.root.update_idletasks()
            app._set_status("error", detail="timeout")
            app.root.update_idletasks()
            self.assertIn("Could not connect", app.status_var.get())
            fg = str(app.status_label.cget("fg")).lower()
            # Tk may return #cd0a0a or system name; must not be the message string
            self.assertNotEqual(fg, "could not connect")
            self.assertTrue(
                fg.startswith("#") or "cd0a0a" in fg.replace(" ", ""),
                f"expected error red hex, got {fg!r}",
            )
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass

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
        self.assertTrue(version_is_behind("0.1.7", "0.1.8"))
        self.assertFalse(version_is_behind("0.1.8", "0.1.8"))
        self.assertFalse(version_is_behind("0.1.9", "0.1.8"))
        self.assertTrue(version_is_behind("0.0.8", "0.1.8"))

    def test_upgrade_available_helpers(self):
        self.assertTrue(upgrade_available("0.1.0", "0.1.8"))
        self.assertFalse(upgrade_available("0.1.8", "0.1.8"))
        msg = upgrade_banner_text("0.1.0", "0.1.8")
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("0.1.0", msg)
        self.assertIn("0.1.8", msg)
        self.assertIsNone(upgrade_banner_text("0.1.8", "0.1.8"))

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


class TestDialogueStatusFlips(unittest.TestCase):
    """Main window status dialogue must track Connect / Disconnect states."""

    def _make_app(self):
        try:
            return TunnelClientApp()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return None

    def test_set_status_connected_updates_dialogue(self):
        app = self._make_app()
        if app is None:
            return
        try:
            app.root.update_idletasks()
            app._set_status(
                "connected", vpn_ip="10.88.0.2", residual_capture=True
            )
            app.root.update_idletasks()
            status = app.status_var.get()
            self.assertIn("Connected", status)
            self.assertIn("10.88.0.2", status)
            detail = app.detail_var.get()
            self.assertIn("residual public ip", detail.lower())
            self.assertIn("vpn", detail.lower())
            self.assertEqual(app.connect_button_text(), "Connect")  # not applied yet
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass

    def test_apply_control_then_status_shows_disconnect_button(self):
        app = self._make_app()
        if app is None:
            return
        try:
            app.root.update_idletasks()
            # Product connect success order
            app._apply_control(connected=True, busy=False)
            app._set_status(
                "connected", vpn_ip="10.88.0.2", residual_capture=True
            )
            app.root.update_idletasks()
            self.assertTrue(app._connected)
            self.assertEqual(app.connect_button_text(), "Disconnect")
            self.assertIn("Connected", app.status_var.get())
            self.assertIn(
                "VPN", app.detail_var.get()
            )
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass

    def test_connecting_and_disconnecting_dialogue(self):
        app = self._make_app()
        if app is None:
            return
        try:
            app.root.update_idletasks()
            app._apply_control(connected=False, busy=True)
            app._set_status("connecting")
            app.root.update_idletasks()
            self.assertIn("Connecting", app.status_var.get())
            self.assertEqual(app.btn_var.get(), "Connecting...")
            self.assertIn("Please wait", app.detail_var.get())

            app._apply_control(connected=True, busy=True)
            app._set_status("disconnecting")
            app.root.update_idletasks()
            self.assertIn("Disconnecting", app.status_var.get())
            self.assertEqual(app.btn_var.get(), "Disconnecting...")
            self.assertIn("Stopping", app.detail_var.get())

            app._apply_control(connected=False, busy=False)
            app._set_status("disconnected")
            app.root.update_idletasks()
            self.assertIn("Disconnected", app.status_var.get())
            self.assertEqual(app.connect_button_text(), "Connect")
            self.assertIn("Not connected", app.detail_var.get())
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass

    def test_set_status_pushes_explicit_tray_flags(self):
        """_set_status must pass connected= so tray never uses stale _connected."""
        app = self._make_app()
        if app is None:
            return
        try:
            mock_tray = mock.Mock()
            app._tray = mock_tray
            app._connected = False  # stale / pre-apply_control

            app._set_status(
                "connected", vpn_ip="10.88.0.2", residual_capture=True
            )
            mock_tray.update_status.assert_called_with(
                connected=True, residual=True
            )

            app._set_status("disconnected")
            mock_tray.update_status.assert_called_with(
                connected=False, residual=False
            )

            app._set_status("connecting")
            mock_tray.update_status.assert_called_with(
                connected=False, residual=False
            )

            app._set_status("disconnecting")
            mock_tray.update_status.assert_called_with(
                connected=True, residual=True
            )
        finally:
            try:
                app.root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
