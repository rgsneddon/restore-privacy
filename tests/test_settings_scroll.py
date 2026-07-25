"""Settings page wheel/trackpad scroll helpers (shipped ui_chrome + app wiring)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.ui_chrome import (  # noqa: E402
    apply_canvas_wheel_scroll,
    bind_scrollable_canvas,
    mousewheel_event_scroll_units,
    wheel_delta_to_scroll_units,
)


class TestWheelScrollUnits(unittest.TestCase):
    def test_windows_mousewheel_delta(self):
        # Positive delta = scroll up → negative yview units
        self.assertEqual(wheel_delta_to_scroll_units(120), -1)
        self.assertEqual(wheel_delta_to_scroll_units(-120), 1)
        self.assertEqual(wheel_delta_to_scroll_units(240), -2)

    def test_x11_buttons(self):
        self.assertEqual(wheel_delta_to_scroll_units(num=4), -3)
        self.assertEqual(wheel_delta_to_scroll_units(num=5), 3)

    def test_event_adapter(self):
        self.assertEqual(
            mousewheel_event_scroll_units(SimpleNamespace(delta=120, num=None)),
            -1,
        )
        self.assertEqual(
            mousewheel_event_scroll_units(SimpleNamespace(delta=0, num=5)),
            3,
        )
        self.assertEqual(
            mousewheel_event_scroll_units(SimpleNamespace(delta=0, num=None)),
            0,
        )


class TestApplyCanvasScroll(unittest.TestCase):
    def test_yview_scroll_called(self):
        canvas = mock.Mock()
        self.assertTrue(apply_canvas_wheel_scroll(canvas, -2))
        canvas.yview_scroll.assert_called_once_with(-2, "units")

    def test_zero_units_noop(self):
        canvas = mock.Mock()
        self.assertFalse(apply_canvas_wheel_scroll(canvas, 0))
        canvas.yview_scroll.assert_not_called()


class TestBindScrollableCanvas(unittest.TestCase):
    def test_bind_and_unbind_sequences(self):
        canvas = mock.Mock()
        pad = mock.Mock()
        pad.winfo_children.return_value = []
        unbind = bind_scrollable_canvas(canvas, pad)
        # Canvas receives MouseWheel + Button-4/5
        bound_seqs = [c.args[0] for c in canvas.bind.call_args_list]
        self.assertIn("<MouseWheel>", bound_seqs)
        self.assertIn("<Button-4>", bound_seqs)
        self.assertIn("<Button-5>", bound_seqs)
        # Enter/Leave for bind_all path
        enter_leave = [c.args[0] for c in canvas.bind.call_args_list]
        self.assertIn("<Enter>", enter_leave)
        self.assertIn("<Leave>", enter_leave)
        unbind()
        self.assertTrue(canvas.unbind.called or canvas.unbind_all.called)


class TestSettingsAppWiring(unittest.TestCase):
    def test_open_settings_binds_scrollable_canvas(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("bind_scrollable_canvas", src)
        self.assertIn("_settings_scroll_unbind", src)
        # Scrollable canvas still present with scrollbar
        self.assertIn("tk.Canvas", src)
        self.assertIn("tk.Scrollbar", src)
        self.assertIn("yscrollcommand", src)
        # Wheel path uses real helper
        self.assertIn("bind_scrollable_canvas(canvas, pad, win)", src)


if __name__ == "__main__":
    unittest.main()
