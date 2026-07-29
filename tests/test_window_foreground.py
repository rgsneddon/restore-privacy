"""Windows shell foreground policy: pure helpers + packaging smoke."""

from __future__ import annotations

import ast
import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestWindowForegroundImport(unittest.TestCase):
    def test_module_importable_and_exports_bring_tk(self) -> None:
        mod = importlib.import_module("client.windows.window_foreground")
        self.assertTrue(callable(getattr(mod, "bring_tk_window_forward")))
        self.assertTrue(callable(getattr(mod, "should_raise_window")))
        self.assertTrue(callable(getattr(mod, "normalize_wm_state")))

    def test_app_py_imports_shipped_module(self) -> None:
        """app.py top-level import must resolve to the restored module file."""
        app_path = ROOT / "client" / "windows" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        self.assertIn(
            "from client.windows.window_foreground import bring_tk_window_forward",
            src,
        )
        # Real import path used by the client entry (same as frozen app.py).
        from client.windows.window_foreground import bring_tk_window_forward

        self.assertTrue(callable(bring_tk_window_forward))


class TestForegroundPolicyHelpers(unittest.TestCase):
    def test_normalize_wm_state_aliases(self) -> None:
        from client.windows.window_foreground import normalize_wm_state

        self.assertEqual(normalize_wm_state("iconic"), "iconic")
        self.assertEqual(normalize_wm_state("minimized"), "iconic")
        self.assertEqual(normalize_wm_state("withdrawn"), "withdrawn")
        self.assertEqual(normalize_wm_state("zoomed"), "zoomed")
        self.assertEqual(normalize_wm_state("normal"), "normal")
        self.assertEqual(normalize_wm_state(None), "normal")
        self.assertEqual(normalize_wm_state(""), "normal")

    def test_should_raise_visible_shell(self) -> None:
        from client.windows.window_foreground import should_raise_window

        d = should_raise_window(viewable=True, wm_state="normal", force_visible=False)
        self.assertTrue(d.should_raise)
        self.assertEqual(d.reason, "visible_active_shell")

    def test_should_skip_withdrawn_and_iconic_without_force(self) -> None:
        from client.windows.window_foreground import should_raise_window

        w = should_raise_window(
            viewable=False, wm_state="withdrawn", force_visible=False
        )
        self.assertFalse(w.should_raise)
        self.assertEqual(w.reason, "withdrawn_user_tray")

        i = should_raise_window(viewable=False, wm_state="iconic", force_visible=False)
        self.assertFalse(i.should_raise)
        self.assertEqual(i.reason, "iconic_user_minimized")

    def test_force_visible_raises_even_if_withdrawn(self) -> None:
        from client.windows.window_foreground import should_raise_window

        d = should_raise_window(
            viewable=False, wm_state="withdrawn", force_visible=True
        )
        self.assertTrue(d.should_raise)
        self.assertTrue(d.force_visible)
        self.assertEqual(d.reason, "force_visible")

    def test_not_viewable_skips_without_force(self) -> None:
        from client.windows.window_foreground import should_raise_window

        d = should_raise_window(viewable=False, wm_state="normal", force_visible=False)
        self.assertFalse(d.should_raise)
        self.assertEqual(d.reason, "not_viewable")

    def test_bring_tk_window_forward_none_and_destroyed(self) -> None:
        from client.windows.window_foreground import bring_tk_window_forward

        self.assertEqual(bring_tk_window_forward(None), "skipped:no_window")

        class _Gone:
            def winfo_exists(self) -> bool:
                return False

        self.assertEqual(bring_tk_window_forward(_Gone()), "skipped:destroyed")

    def test_bring_tk_window_forward_skips_withdrawn_shell(self) -> None:
        from client.windows.window_foreground import bring_tk_window_forward

        class _Withdrawn:
            def winfo_exists(self) -> bool:
                return True

            def winfo_viewable(self) -> bool:
                return False

            def state(self) -> str:
                return "withdrawn"

        note = bring_tk_window_forward(_Withdrawn(), force_visible=False)
        self.assertEqual(note, "skipped:withdrawn_user_tray")

    def test_bring_tk_window_forward_raises_visible_shell(self) -> None:
        from client.windows.window_foreground import bring_tk_window_forward

        cleared: list[bool] = []

        class _Visible:
            def winfo_exists(self) -> bool:
                return True

            def winfo_viewable(self) -> bool:
                return True

            def state(self) -> str:
                return "normal"

            def lift(self) -> None:
                pass

            def attributes(self, *args, **kwargs) -> None:
                pass

            def update_idletasks(self) -> None:
                pass

            def focus_force(self) -> None:
                pass

            def after(self, ms: int, cb) -> None:
                # Invoke clear immediately so test exercises pulse path.
                cleared.append(True)
                cb()

            def winfo_id(self) -> int:
                return 0

        note = bring_tk_window_forward(_Visible(), force_visible=False, pulse_ms=50)
        self.assertTrue(note.startswith("raised:"), note)
        self.assertEqual(note, "raised:visible_active_shell")
        self.assertTrue(cleared)


class TestWindowForegroundPackaging(unittest.TestCase):
    def test_source_file_tracked_and_not_pyc_only(self) -> None:
        path = ROOT / "client" / "windows" / "window_foreground.py"
        self.assertTrue(path.is_file(), f"missing {path}")
        src = path.read_text(encoding="utf-8")
        self.assertIn("def bring_tk_window_forward", src)
        self.assertIn("def should_raise_window", src)
        # Parse as real Python (not a leftover cache stub).
        tree = ast.parse(src)
        names = {
            n.name
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        self.assertIn("bring_tk_window_forward", names)
        self.assertIn("should_raise_window", names)
        self.assertIn("normalize_wm_state", names)

    def test_pyinstaller_recipe_lists_hidden_import(self) -> None:
        recipe = (ROOT / "scripts" / "build_release_0.0.8.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("client.windows.window_foreground", recipe)
        self.assertIn("--hidden-import", recipe)

    def test_multihop_build_check_requires_module_file(self) -> None:
        bat = (ROOT / "scripts" / "build_windows_multihop.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("window_foreground.py", bat)
        self.assertIn("bring_tk_window_forward", bat)


if __name__ == "__main__":
    unittest.main()
