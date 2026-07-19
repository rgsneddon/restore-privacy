"""Privacy Restored tray identity + logo shortcuts / brand assets.

Also covers Connect/Disconnect tray tip+icon state flips (NIF_TIP|NIF_ICON).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.tray_win import (  # noqa: E402
    TRAY_DISPLAY_NAME,
    WindowsSystemTray,
    make_status_icon_handle,
    resolve_tray_icon_path,
    tray_icon_state_key,
    tray_tooltip_for_state,
)
from client.windows.installer import (  # noqa: E402
    SHORTCUT_DISPLAY_NAME,
    resolve_shortcut_icon,
)


class TestTrayBranding(unittest.TestCase):
    def test_tray_display_name_is_privacy_restored(self):
        self.assertEqual(TRAY_DISPLAY_NAME, "Privacy Restored")

    def test_tray_tooltip_uses_product_name(self):
        tip = tray_tooltip_for_state(connected=True, residual=True)
        self.assertIn("Privacy Restored", tip)
        self.assertIn("connected", tip.lower())
        tip2 = tray_tooltip_for_state(connected=False)
        self.assertIn("Privacy Restored", tip2)
        self.assertIn("disconnected", tip2.lower())

    def test_tray_tooltip_session_only(self):
        tip = tray_tooltip_for_state(connected=True, residual=False)
        self.assertIn("session only", tip.lower())
        self.assertNotIn("disconnected", tip.lower())

    def test_tray_icon_state_key(self):
        self.assertEqual(
            tray_icon_state_key(connected=True, residual=True), "connected"
        )
        self.assertEqual(
            tray_icon_state_key(connected=True, residual=False), "session_only"
        )
        self.assertEqual(tray_icon_state_key(connected=False), "disconnected")

    def test_tray_icon_resolves_to_logo_file(self):
        p = resolve_tray_icon_path()
        self.assertIsNotNone(p)
        assert p is not None
        self.assertTrue(p.is_file())
        self.assertTrue(p.suffix.lower() in (".ico", ".png"))

    def test_app_wires_tray(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("WindowsSystemTray", src)
        self.assertIn("TRAY_DISPLAY_NAME", src)
        self.assertIn("_start_system_tray", src)
        self.assertIn("Privacy Restored", src)  # log / close message uses tray name


class TestTrayStatusUpdate(unittest.TestCase):
    """Tray tip+icon must flip with Connect/Disconnect (not stuck on disconnected)."""

    def test_update_status_mutates_tooltip_and_flags(self):
        tray = WindowsSystemTray(
            on_show=lambda: None,
            on_quit=lambda: None,
        )
        self.assertFalse(tray._connected)
        self.assertIn("disconnected", tray._tooltip.lower())

        tray.update_status(connected=True, residual=True)
        self.assertTrue(tray._connected)
        self.assertTrue(tray._residual)
        self.assertIn("connected", tray._tooltip.lower())
        self.assertNotIn("disconnected", tray._tooltip.lower())
        self.assertEqual(tray._pending, (True, True))

        tray.update_status(connected=False, residual=False)
        self.assertFalse(tray._connected)
        self.assertIn("disconnected", tray._tooltip.lower())
        self.assertEqual(tray._pending, (False, False))

    def test_update_status_posts_modify_when_hwnd_ready(self):
        tray = WindowsSystemTray(
            on_show=lambda: None,
            on_quit=lambda: None,
        )
        tray._running = True
        tray._hwnd = 0x1234  # non-None sentinel
        tray._hicon_connected = 111
        tray._hicon_disconnected = 222
        with mock.patch("ctypes.windll.user32.PostMessageW") as post:
            tray.update_status(connected=True, residual=True)
            post.assert_called()
            # WM_USER+99
            args = post.call_args[0]
            self.assertEqual(args[0], 0x1234)
            self.assertEqual(args[1], 0x0400 + 99)

    def test_apply_notify_modify_sets_tip_and_icon_flags(self):
        tray = WindowsSystemTray(
            on_show=lambda: None,
            on_quit=lambda: None,
        )
        tray._running = True
        tray._hwnd = 1
        tray._hicon_connected = 99
        tray._hicon_disconnected = 88
        tray._connected = True
        tray._residual = True
        tray._tooltip = tray_tooltip_for_state(connected=True, residual=True)

        captured = {}

        def fake_notify(cmd, nid_ref):
            nid = nid_ref._obj
            captured["cmd"] = cmd
            captured["flags"] = int(nid.uFlags)
            captured["tip"] = str(nid.szTip)
            captured["hicon"] = int(nid.hIcon)
            return 1

        with mock.patch(
            "ctypes.windll.shell32.Shell_NotifyIconW", side_effect=fake_notify
        ):
            tray._apply_notify_modify()

        NIF_ICON = 0x00000002
        NIF_TIP = 0x00000004
        NIM_MODIFY = 0x00000001
        self.assertEqual(captured.get("cmd"), NIM_MODIFY)
        self.assertEqual(captured.get("flags"), NIF_TIP | NIF_ICON)
        self.assertIn("connected", (captured.get("tip") or "").lower())
        self.assertEqual(captured.get("hicon"), 99)

        # Disconnect flips to grey icon handle
        tray._connected = False
        tray._residual = False
        tray._tooltip = tray_tooltip_for_state(connected=False)
        with mock.patch(
            "ctypes.windll.shell32.Shell_NotifyIconW", side_effect=fake_notify
        ):
            tray._apply_notify_modify()
        self.assertIn("disconnected", (captured.get("tip") or "").lower())
        self.assertEqual(captured.get("hicon"), 88)

    def test_make_status_icon_handle_returns_hicon_on_windows(self):
        if sys.platform != "win32":
            self.skipTest("Windows only")
        h_disc = make_status_icon_handle(connected=False)
        h_conn = make_status_icon_handle(connected=True, residual=True)
        self.assertTrue(h_disc, "disconnected HICON expected")
        self.assertTrue(h_conn, "connected HICON expected")
        self.assertNotEqual(h_disc, h_conn)
        # Destroy to avoid GDI leak in test process
        import ctypes

        ctypes.windll.user32.DestroyIcon(h_disc)
        ctypes.windll.user32.DestroyIcon(h_conn)

    def test_app_source_syncs_tray_on_connect_disconnect(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _sync_tray_status", src)
        self.assertIn("connected=True", src)
        self.assertIn("connected=False", src)
        # Connect success: apply_control before set_status so _connected is True
        conn = src[src.index("def _start_connect") : src.index("def _start_disconnect")]
        apply_idx = conn.index("self._apply_control(connected=True, busy=False)")
        status_idx = conn.index('self._set_status(\n                            "connected"')
        self.assertLess(apply_idx, status_idx)
        # Disconnect done path forces tray disconnected
        disc = src[src.index("def _start_disconnect") : src.index("def _open_upgrade")]
        self.assertIn("_sync_tray_status(connected=False", disc)
        self.assertIn('self._set_status("disconnected")', disc)
        # _set_status always pushes explicit connected= for every state
        set_status = src[src.index("def _set_status") : src.index("def _apply_control")]
        self.assertIn("_sync_tray_status(connected=True", set_status)
        self.assertIn("_sync_tray_status(connected=False", set_status)


class TestShortcutLogo(unittest.TestCase):
    def test_shortcut_display_name(self):
        self.assertEqual(SHORTCUT_DISPLAY_NAME, "Privacy Restored")

    def test_installer_sets_icon_location(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("IconLocation", src)
        self.assertIn("SHORTCUT_DISPLAY_NAME", src)
        self.assertIn("resolve_shortcut_icon", src)
        self.assertIn("app_icon.ico", src)

    def test_resolve_shortcut_icon_prefers_ico(self):
        native = ROOT / "client" / "windows" / "native"
        ico = native / "app_icon.ico"
        self.assertTrue(ico.is_file())
        # When install dir is native folder, returns ico
        got = resolve_shortcut_icon(native, native / "missing.exe")
        self.assertEqual(got.suffix.lower(), ".ico")


class TestBrandAssetsPresent(unittest.TestCase):
    def test_favicon_and_logo_exist(self):
        brand = ROOT / "assets" / "brand"
        for name in ("favicon.ico", "logo-256.png", "vpnlogo.jpg"):
            self.assertTrue((brand / name).is_file(), name)
        self.assertTrue(
            (ROOT / "client" / "windows" / "native" / "app_icon.ico").is_file()
        )
        self.assertTrue(
            (ROOT / "status_page" / "static" / "favicon.ico").is_file()
        )


if __name__ == "__main__":
    unittest.main()
