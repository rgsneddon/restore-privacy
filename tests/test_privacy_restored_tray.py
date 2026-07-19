"""Privacy Restored tray identity + logo shortcuts / brand assets."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.tray_win import (  # noqa: E402
    TRAY_DISPLAY_NAME,
    resolve_tray_icon_path,
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
