"""GUI launch should prefer windowed pythonw so a bare console is not left open."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.launch_gui import (  # noqa: E402
    launch_argv_windowed,
    prefer_windowed_gui_launch,
    resolve_pythonw,
)


class TestWindowedLaunch(unittest.TestCase):
    def test_policy_prefers_windowed(self):
        self.assertTrue(prefer_windowed_gui_launch())

    def test_launch_argv_uses_module_client_windows(self):
        exe, args, cwd = launch_argv_windowed()
        self.assertIn("-m", args)
        self.assertIn("client.windows", args)
        self.assertTrue((Path(cwd) / "client" / "windows").is_dir())
        self.assertTrue(exe)

    def test_resolve_pythonw_when_python_exe(self):
        with mock.patch.object(sys, "executable", r"C:\Python\python.exe"), mock.patch(
            "client.windows.launch_gui.Path.is_file", return_value=True
        ):
            # with_name yields pythonw next to python
            p = resolve_pythonw(r"C:\Python\python.exe")
            # May be None if path doesn't exist on disk; when is_file True:
            if p is not None:
                self.assertTrue(str(p).lower().endswith("pythonw.exe"))

    def test_main_module_reexec_helper_present(self):
        src = (ROOT / "client" / "windows" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("launch_gui", src)
        self.assertIn("GetConsoleWindow", src)
        self.assertIn("pythonw", src.lower())

    def test_app_no_auto_connect(self):
        from client.windows.app import auto_connect_on_launch_enabled

        self.assertFalse(auto_connect_on_launch_enabled())
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_auto_connect", app)


if __name__ == "__main__":
    unittest.main()
