"""1.2.4 Windows chrome mimics Evolve palette and hero-orb states.

Drives shipped ``theme_tokens`` / ``hero_orb_palette`` / ``HeroStatusOrb.set_state``
— not a parallel re-implementation of the colors.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.ui_theme import (  # noqa: E402
    DEFAULT_UI_MODE,
    EVOLVE_ACCENT,
    EVOLVE_BG,
    EVOLVE_CARD,
    EVOLVE_SECONDARY,
    EVOLVE_TEXT,
    UI_MODE_DARK,
    hero_orb_palette,
    theme_tokens,
)


class TestEvolvePaletteShipped(unittest.TestCase):
    def test_dark_tokens_are_evolve_desktop(self) -> None:
        dark = theme_tokens(UI_MODE_DARK)
        self.assertEqual(DEFAULT_UI_MODE, UI_MODE_DARK)
        self.assertEqual(dark["chrome_bg"], EVOLVE_BG)
        self.assertEqual(dark["panel_bg"], EVOLVE_CARD)
        self.assertEqual(dark["primary"], EVOLVE_ACCENT)
        self.assertEqual(dark["status_ok"], EVOLVE_SECONDARY)
        self.assertEqual(dark["text"], EVOLVE_TEXT)
        self.assertEqual(dark["neon_border"], EVOLVE_ACCENT)
        self.assertNotEqual(dark["status_ok"], dark["status_error"])

    def test_hero_orb_palette_connected_uses_teal(self) -> None:
        dark = theme_tokens(UI_MODE_DARK)
        connected = hero_orb_palette("connected", dark)
        self.assertEqual(connected["ring"], dark["status_ok"])
        self.assertEqual(connected["dot"], dark["status_ok"])
        idle = hero_orb_palette("disconnected", dark)
        self.assertEqual(idle["ring"], dark["border"])
        self.assertNotEqual(connected["ring"], idle["ring"])
        connecting = hero_orb_palette("connecting", dark)
        self.assertEqual(connecting["ring"], dark["primary"])
        err = hero_orb_palette("error", dark)
        self.assertEqual(err["ring"], dark["status_error"])

    def test_hero_orb_widget_draws_shipped_palette(self) -> None:
        import tkinter as tk

        from client.windows.ui_chrome import HeroStatusOrb

        root = tk.Tk()
        root.withdraw()
        try:
            orb = HeroStatusOrb(root, size=64, bg=EVOLVE_CARD)
            orb.set_state("connected", tokens=theme_tokens(UI_MODE_DARK))
            self.assertEqual(orb._state, "connected")
            # Canvas must have the ring/core/dot items from _draw
            ids = orb.canvas.find_all()
            self.assertGreaterEqual(len(ids), 3)
            fills = [orb.canvas.itemcget(i, "fill") for i in ids]
            self.assertIn(EVOLVE_SECONDARY, fills)
        finally:
            root.destroy()

    def test_app_wires_hero_orb_and_accent_bar(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("HeroStatusOrb", src)
        self.assertIn("self.hero_orb", src)
        self.assertIn("self.accent_bar", src)
        self.assertIn("orb.set_state", src)
        # Product truth: residual VPN chrome, not Evolve product tabs
        self.assertNotIn("kSuiteTabEvolve", src)
        self.assertNotIn("Perccent", src)


if __name__ == "__main__":
    unittest.main()
