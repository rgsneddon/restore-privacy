"""Windows UI chrome: center placement, size floors, neon boxes, switches."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestCenterAndSizeHelpers(unittest.TestCase):
    def test_center_geometry_centers_on_work_area(self) -> None:
        from client.windows.ui_chrome import center_geometry, parse_size

        geo = center_geometry(600, 400, 1920, 1080)
        w, h = parse_size(geo)
        self.assertEqual((w, h), (600, 400))
        # Format WxH+X+Y
        self.assertIn("+", geo)
        body, pos = geo.split("+", 1)
        x_s, y_s = pos.split("+")
        x, y = int(x_s), int(y_s)
        self.assertEqual(x, (1920 - 600) // 2)
        self.assertEqual(y, (1080 - 400) // 2)
        # Fully on screen
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, 1920)
        self.assertLessEqual(y + h, 1080)

    def test_center_geometry_keeps_window_on_small_screen(self) -> None:
        from client.windows.ui_chrome import center_geometry, parse_size

        geo = center_geometry(800, 600, 800, 600)
        w, h = parse_size(geo)
        self.assertEqual((w, h), (800, 600))
        # With min_margin 8, x/y should be >= 8 or 0 if forced
        self.assertRegex(geo, r"^800x600\+\d+\+\d+$")

    def test_surface_size_floors_large_enough(self) -> None:
        from client.windows.ui_chrome import (
            surface_default_size,
            surface_min_size,
        )

        for surface, min_w, min_h in (
            ("main", 560, 600),
            ("licence", 520, 480),
            ("keygen", 520, 420),
            ("settings", 600, 760),
            ("settings_first_run", 620, 780),
        ):
            dw, dh = surface_default_size(surface)
            mw, mh = surface_min_size(surface)
            self.assertGreaterEqual(dw, min_w, surface)
            self.assertGreaterEqual(dh, min_h, surface)
            self.assertGreaterEqual(mw, min_w, surface)
            self.assertGreaterEqual(mh, min_h, surface)
            self.assertGreaterEqual(dw, mw)
            self.assertGreaterEqual(dh, mh)

    def test_first_run_geometry_constants_align(self) -> None:
        from client.first_run_flow import (
            FIRST_RUN_SETTINGS_GEOMETRY,
            FIRST_RUN_SETTINGS_MINSIZE,
            MAIN_CONNECT_GEOMETRY,
        )
        from client.windows.ui_chrome import parse_size, surface_default_size

        mw, mh = parse_size(MAIN_CONNECT_GEOMETRY)
        self.assertEqual((mw, mh), surface_default_size("main"))
        sw, sh = parse_size(FIRST_RUN_SETTINGS_GEOMETRY)
        self.assertEqual((sw, sh), surface_default_size("settings_first_run"))
        self.assertEqual(
            FIRST_RUN_SETTINGS_MINSIZE,
            __import__(
                "client.windows.ui_chrome", fromlist=["surface_min_size"]
            ).surface_min_size("settings_first_run"),
        )


class TestNeonAndSwitchStructural(unittest.TestCase):
    def test_neon_and_switch_in_shipped_modules(self) -> None:
        chrome = (
            ROOT / "client" / "windows" / "ui_chrome.py"
        ).read_text(encoding="utf-8")
        self.assertIn("NEON_BORDER", chrome)
        self.assertIn("make_neon_card", chrome)
        self.assertIn("class SwitchToggle", chrome)
        self.assertIn("center_geometry", chrome)
        self.assertIn("apply_centered_window", chrome)

        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("apply_centered_window", app)
        self.assertIn("make_neon_card", app)
        self.assertIn("SwitchToggle", app)
        # Settings booleans use switch, not Checkbutton in _row
        self.assertIn("SwitchToggle(", app)
        # Center main + modals
        self.assertIn('surface="main"', app)
        self.assertIn('surface="licence"', app)
        self.assertIn('surface="keygen"', app)
        self.assertIn("settings_first_run", app)
        self.assertIn("settings", app)
        self.assertIn("apply_centered_window", app)

    def test_switch_toggle_constructs_with_tk(self) -> None:
        import tkinter as tk

        from client.windows.ui_chrome import SwitchToggle

        root = tk.Tk()
        root.withdraw()
        try:
            var = tk.BooleanVar(value=False)
            sw = SwitchToggle(root, var)
            self.assertFalse(var.get())
            sw._on_click()
            self.assertTrue(var.get())
            sw._on_click()
            self.assertFalse(var.get())
            # Canvas present (pill control)
            self.assertTrue(hasattr(sw, "canvas"))
            self.assertGreater(sw.canvas.winfo_reqwidth(), 40)
        finally:
            root.destroy()

    def test_make_neon_card_layers(self) -> None:
        import tkinter as tk

        from client.windows.ui_chrome import NEON_BORDER, make_neon_card

        root = tk.Tk()
        root.withdraw()
        try:
            inner, outer = make_neon_card(root)
            self.assertEqual(outer.cget("bg"), NEON_BORDER)
            self.assertIsNotNone(inner)
            outer.pack()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
