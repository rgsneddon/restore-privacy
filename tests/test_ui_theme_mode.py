"""Dark/light UI mode tokens + durable settings preference (shipped helpers)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.ui_theme import (  # noqa: E402
    UI_MODE_DARK,
    UI_MODE_LIGHT,
    normalize_ui_mode,
    theme_tokens,
    theme_toggle_button_text,
    theme_toggle_target,
)
from client.windows.settings_store import (  # noqa: E402
    KEY_UI_MODE,
    ProductSettings,
    default_settings,
    load_settings,
    save_settings,
)


class TestThemeTokens(unittest.TestCase):
    def test_normalize_default_light(self):
        self.assertEqual(normalize_ui_mode(None), UI_MODE_LIGHT)
        self.assertEqual(normalize_ui_mode(""), UI_MODE_LIGHT)
        self.assertEqual(normalize_ui_mode("weird"), UI_MODE_LIGHT)
        self.assertEqual(normalize_ui_mode("DARK"), UI_MODE_DARK)

    def test_light_and_dark_maps_differ(self):
        light = theme_tokens(UI_MODE_LIGHT)
        dark = theme_tokens(UI_MODE_DARK)
        self.assertNotEqual(light["chrome_bg"], dark["chrome_bg"])
        self.assertNotEqual(light["panel_bg"], dark["panel_bg"])
        self.assertNotEqual(light["text"], dark["text"])
        # Status semantics remain present and distinct within each mode
        self.assertNotEqual(light["status_ok"], light["status_error"])
        self.assertNotEqual(dark["status_ok"], dark["status_error"])

    def test_toggle_helpers(self):
        self.assertEqual(theme_toggle_target(UI_MODE_LIGHT), UI_MODE_DARK)
        self.assertEqual(theme_toggle_target(UI_MODE_DARK), UI_MODE_LIGHT)
        self.assertIn("Dark", theme_toggle_button_text(UI_MODE_LIGHT))
        self.assertIn("Light", theme_toggle_button_text(UI_MODE_DARK))


class TestUiModePersistence(unittest.TestCase):
    def test_default_ui_mode_light(self):
        d = default_settings()
        self.assertEqual(normalize_ui_mode(d.ui_mode), UI_MODE_LIGHT)

    def test_save_load_ui_mode_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = ProductSettings(ui_mode=UI_MODE_DARK)
            save_settings(s, path=path)
            loaded = load_settings(path=path)
            self.assertEqual(loaded.ui_mode, UI_MODE_DARK)
            raw = path.read_text(encoding="utf-8")
            self.assertIn(KEY_UI_MODE, raw)
            self.assertIn("dark", raw)

            s2 = ProductSettings(ui_mode=UI_MODE_LIGHT)
            save_settings(s2, path=path)
            self.assertEqual(load_settings(path=path).ui_mode, UI_MODE_LIGHT)

    def test_missing_ui_mode_key_defaults_light(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text(
                '{"run_at_startup": false, "autoconnect_on_launch": false}\n',
                encoding="utf-8",
            )
            loaded = load_settings(path=path)
            self.assertEqual(loaded.ui_mode, UI_MODE_LIGHT)


class TestMainWindowThemeStructure(unittest.TestCase):
    def test_app_header_has_theme_btn_beside_settings(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("self.theme_btn", src)
        self.assertIn("self.settings_btn", src)
        self.assertIn("_toggle_ui_mode", src)
        self.assertIn("theme_toggle_button_text", src)
        self.assertIn("theme_tokens", src)
        # Same header parent + pack side RIGHT family as the gear
        gear_pack = src.index("self.settings_btn.pack(side=tk.RIGHT)")
        theme_pack = src.index("self.theme_btn.pack(side=tk.RIGHT")
        # Both in header build region near each other
        self.assertLess(abs(gear_pack - theme_pack), 800)
        self.assertIn('self.header', src[min(gear_pack, theme_pack) - 400 : max(gear_pack, theme_pack) + 200])


if __name__ == "__main__":
    unittest.main()
