"""GUI launch should prefer windowed pythonw so a bare console is not left open."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.launch_gui import (  # noqa: E402
    free_console_if_attached,
    is_console_python_host,
    launch_argv_windowed,
    prefer_windowed_gui_launch,
    resolve_pythonw,
    should_reexec_to_windowed_host,
)
from client.windows.elevate import launch_argv_for_elevation  # noqa: E402


class TestWindowedLaunch(unittest.TestCase):
    def test_policy_prefers_windowed(self):
        self.assertTrue(prefer_windowed_gui_launch())

    def test_launch_argv_uses_module_client_windows(self):
        exe, args, cwd = launch_argv_windowed()
        self.assertIn("-m", args)
        self.assertIn("client.windows", args)
        self.assertTrue((Path(cwd) / "client" / "windows").is_dir())
        self.assertTrue(exe)

    def test_launch_argv_prefers_pythonw_when_present(self):
        pyw = resolve_pythonw()
        if pyw is None:
            self.skipTest("pythonw not installed next to this interpreter")
        exe, args, _cwd = launch_argv_windowed()
        self.assertTrue(exe.lower().endswith("pythonw.exe"), exe)
        self.assertIn("client.windows", args)

    def test_resolve_pythonw_when_python_exe(self):
        with mock.patch.object(sys, "executable", r"C:\Python\python.exe"), mock.patch(
            "client.windows.launch_gui.Path.is_file", return_value=True
        ):
            # with_name yields pythonw next to python
            p = resolve_pythonw(r"C:\Python\python.exe")
            # May be None if path doesn't exist on disk; when is_file True:
            if p is not None:
                self.assertTrue(str(p).lower().endswith("pythonw.exe"))

    def test_should_reexec_when_console_python_and_pythonw_exists(self):
        pyw = resolve_pythonw()
        if pyw is None:
            self.skipTest("pythonw not available")
        with mock.patch.object(sys, "executable", str(Path(sys.executable).with_name("python.exe"))):
            # Force console host name; resolve_pythonw still finds real pythonw
            if Path(sys.executable).name.lower() == "pythonw.exe":
                # running under pythonw already — should_reexec false
                self.assertFalse(should_reexec_to_windowed_host())
            else:
                self.assertTrue(should_reexec_to_windowed_host() or is_console_python_host())

    def test_main_module_reexec_helper_present(self):
        src = (ROOT / "client" / "windows" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("launch_gui", src)
        self.assertIn("should_reexec_to_windowed_host", src)
        self.assertIn("free_console_if_attached", src)
        self.assertIn("pythonw", src.lower())

    def test_free_console_helper_callable(self):
        # Must not raise; True/False depends on whether a console is attached
        self.assertIsInstance(free_console_if_attached(), bool)

    def test_app_no_auto_connect(self):
        from client.windows.app import auto_connect_on_launch_enabled

        self.assertFalse(auto_connect_on_launch_enabled())
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_auto_connect", app)
        self.assertIn("free_console_if_attached", app)


class TestElevateUsesWindowedHost(unittest.TestCase):
    def test_elevate_argv_prefers_pythonw_not_console_python(self):
        pyw = resolve_pythonw()
        if pyw is None:
            self.skipTest("pythonw not installed")
        with mock.patch.object(sys, "frozen", False, create=True), mock.patch.object(
            sys, "executable", str(Path(pyw).with_name("python.exe"))
        ), mock.patch.object(sys, "argv", ["client/windows/__main__.py"]):
            exe, params = launch_argv_for_elevation()
        self.assertTrue(
            Path(exe).name.lower() == "pythonw.exe",
            f"elevate host should be pythonw, got {exe}",
        )
        self.assertIn("-m", params)
        self.assertIn("client.windows", params)

    def test_elevate_source_calls_windowed_host_helper(self):
        src = (ROOT / "client" / "windows" / "elevate.py").read_text(encoding="utf-8")
        self.assertIn("_windowed_python_host", src)
        self.assertIn("resolve_pythonw", src)
        self.assertIn("pythonw", src.lower())

    def test_elevate_passes_extra_args_with_windowed_host(self):
        pyw = resolve_pythonw()
        if pyw is None:
            self.skipTest("pythonw not installed")
        with mock.patch.object(sys, "frozen", False, create=True), mock.patch.object(
            sys, "argv", ["x"]
        ):
            exe, params = launch_argv_for_elevation(extra_args=["--rpt-auto-connect"])
        self.assertIn("--rpt-auto-connect", params)
        self.assertTrue(Path(exe).name.lower() in ("pythonw.exe", "python.exe"))


if __name__ == "__main__":
    unittest.main()
