"""Windows GUI launch helpers — real spawn/re-exec path (no silent crash)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestLaunchGuiHelpers(unittest.TestCase):
    def test_creation_flag_sets_include_fallback_without_breakaway(self) -> None:
        from client.windows.launch_gui import (
            _CREATE_BREAKAWAY_FROM_JOB,
            _creation_flag_sets,
        )

        sets = _creation_flag_sets()
        self.assertGreaterEqual(len(sets), 2)
        labels = [label for label, _flags in sets]
        # First attempt may use breakaway; a later set must not require it
        self.assertTrue(any(_CREATE_BREAKAWAY_FROM_JOB & flags for _, flags in sets))
        self.assertTrue(
            any(not (_CREATE_BREAKAWAY_FROM_JOB & flags) for _, flags in sets),
            msg="must fall back when CREATE_BREAKAWAY_FROM_JOB is denied",
        )
        self.assertIn("detached+no_window", labels)
        self.assertIn("none", labels)

    def test_spawn_retries_after_breakaway_access_denied(self) -> None:
        """WinError 5 on breakaway must not abort spawn — retry without it."""
        from client.windows import launch_gui as lg

        calls: list[int] = []

        class FakeProc:
            def __init__(self, pid: int = 4242) -> None:
                self.pid = pid
                self._polls = 0

            def poll(self):
                # Stay alive after successful non-breakaway spawn
                return None

        def fake_popen(*_a, **kwargs):
            flags = int(kwargs.get("creationflags") or 0)
            calls.append(flags)
            if flags & lg._CREATE_BREAKAWAY_FROM_JOB:
                raise OSError(5, "Access is denied")
            return FakeProc()

        with mock.patch.object(lg, "should_reexec_to_windowed_host", return_value=True):
            with mock.patch.object(
                lg,
                "launch_argv_windowed",
                return_value=(sys.executable, ["-m", "client.windows"], str(ROOT)),
            ):
                with mock.patch("subprocess.Popen", side_effect=fake_popen):
                    with mock.patch("time.sleep", return_value=None):
                        with mock.patch.object(Path, "is_file", return_value=True):
                            ok = lg.spawn_windowed_gui()
        self.assertTrue(ok)
        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(calls[0] & lg._CREATE_BREAKAWAY_FROM_JOB)
        self.assertFalse(calls[1] & lg._CREATE_BREAKAWAY_FROM_JOB)

    def test_spawn_returns_false_when_not_reexec_host(self) -> None:
        from client.windows import launch_gui as lg

        with mock.patch.object(lg, "should_reexec_to_windowed_host", return_value=False):
            self.assertFalse(lg.spawn_windowed_gui())

    def test_main_returns_nonzero_when_tkinter_missing_after_spawn_fail(self) -> None:
        from client.windows import launch_gui as lg

        with mock.patch.object(lg, "spawn_windowed_gui", return_value=False):
            # Force import failure path
            import builtins

            real_import = builtins.__import__

            def block_tk(name, *a, **kw):
                if name == "tkinter" or name.startswith("tkinter."):
                    raise ImportError("no tk")
                return real_import(name, *a, **kw)

            with mock.patch("builtins.__import__", side_effect=block_tk):
                rc = lg.main()
        self.assertEqual(rc, 1)

    def test_entry_module_uses_spawn_then_inprocess_fallback(self) -> None:
        src = (ROOT / "client" / "windows" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("launch_main", src)
        self.assertIn("_should_reexec_windowed", src)
        gui = (ROOT / "client" / "windows" / "launch_gui.py").read_text(encoding="utf-8")
        self.assertIn("spawn_windowed_gui", gui)
        self.assertIn("_creation_flag_sets", gui)
        self.assertIn("CREATE_BREAKAWAY_FROM_JOB", gui)
        self.assertIn("all flag sets failed", gui)


if __name__ == "__main__":
    unittest.main()
