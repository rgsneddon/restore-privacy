"""Discrete main-screen Quit on Apple residual Flutter shell (macOS + iOS)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestQuitButtonMainScreenWiring(unittest.TestCase):
    def test_app_quit_helper_exists_with_disconnect_then_exit(self):
        src = (ROOT / "client_app" / "lib" / "app_quit.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("performQuitSequence", src)
        self.assertIn("stopTunnel", src)
        self.assertIn("exitApp", src)
        self.assertIn("kQuitButtonLabel", src)
        self.assertIn("bottomRight", src)
        self.assertIn("showsMainScreenQuitButton", src)
        # Order: await stop then exit (not reverse)
        stop_idx = src.index("await stopTunnel()")
        exit_idx = src.index("exitApp()")
        self.assertLess(stop_idx, exit_idx)

    def test_main_connection_screen_wires_quit_bottom_right(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("app_quit.dart", main)
        self.assertIn("kQuitButtonLabel", main)
        self.assertIn("main_quit_button", main)
        self.assertIn("_onQuit", main)
        self.assertIn("performQuitSequence", main)
        self.assertIn("showsMainScreenQuitOnThisDevice", main)
        # Discrete bottom-right placement markers
        self.assertIn("Alignment.centerRight", main)
        self.assertIn("bottomRight", main)
        # Quit uses disconnect-then-exit sequence, not hide-to-tray
        quit_block_start = main.index("Future<void> _onQuit()")
        quit_block = main[quit_block_start : quit_block_start + 900]
        self.assertIn("performQuitSequence", quit_block)
        self.assertIn("disconnect", quit_block)
        self.assertIn("exitAppProcess", quit_block)
        self.assertNotIn("hideToTray", quit_block)

    def test_quit_is_not_primary_connect_cta(self):
        """Quit is TextButton / muted, not the large Connect ElevatedButton."""
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(
            encoding="utf-8"
        )
        # Connect remains ElevatedButton with height 52
        self.assertIn("height: 52", main)
        self.assertIn("ElevatedButton", main)
        # Quit is TextButton with compact density
        self.assertIn("TextButton", main)
        self.assertIn("VisualDensity.compact", main)
        self.assertIn("fontSize: 12", main)

    def test_dart_unit_test_covers_quit_sequence(self):
        dart_test = (
            ROOT / "client_app" / "test" / "app_quit_test.dart"
        ).read_text(encoding="utf-8")
        self.assertIn("performQuitSequence", dart_test)
        self.assertIn("stop", dart_test)
        self.assertIn("exit", dart_test)
        self.assertIn("showsMainScreenQuitButton", dart_test)


if __name__ == "__main__":
    unittest.main()
