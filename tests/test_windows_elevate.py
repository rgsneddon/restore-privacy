"""Auto-elevation helpers — UAC re-launch without manual Run as administrator."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows import elevate as elev  # noqa: E402


class TestElevateHelpers(unittest.TestCase):
    def test_is_admin_callable(self):
        # On this host may be true or false; must not raise
        v = elev.is_admin()
        self.assertIsInstance(v, bool)

    def test_launch_argv_frozen_and_dev(self):
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
            sys, "executable", r"C:\Apps\RestorePrivacy.exe"
        ), mock.patch.object(sys, "argv", [r"C:\Apps\RestorePrivacy.exe", "--foo"]):
            exe, params = elev.launch_argv_for_elevation()
            self.assertTrue(exe.lower().endswith("restoreprivacy.exe"))
            self.assertIn("--foo", params)

        with mock.patch.object(sys, "frozen", False, create=True), mock.patch.object(
            sys, "executable", sys.executable
        ), mock.patch.object(sys, "argv", ["client/windows/__main__.py"]):
            exe, params = elev.launch_argv_for_elevation()
            self.assertIn("python", Path(exe).name.lower() or True)
            self.assertIn("-m", params)
            self.assertIn("client.windows", params)

    def test_elevate_skipped_when_disabled(self):
        with mock.patch.dict(os.environ, {"RPT_NO_AUTO_ELEVATE": "1"}, clear=False):
            self.assertEqual(elev.elevate_if_needed(), "skipped")

    def test_elevate_already_admin(self):
        with mock.patch.dict(os.environ, {"RPT_NO_AUTO_ELEVATE": "0"}, clear=False), mock.patch.object(
            elev, "is_admin", return_value=True
        ):
            os.environ.pop("RPT_NO_AUTO_ELEVATE", None)
            with mock.patch.object(elev, "is_admin", return_value=True):
                self.assertEqual(elev.elevate_if_needed(), "already_admin")

    def test_elevate_relaunches_when_not_admin(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_NO_AUTO_ELEVATE", None)
            with mock.patch.object(elev, "is_admin", return_value=False), mock.patch.object(
                elev, "launch_argv_for_elevation", return_value=(r"C:\x\app.exe", "")
            ), mock.patch.object(elev, "_shell_execute_runas", return_value=42) as se:
                st = elev.elevate_if_needed()
                self.assertEqual(st, "relaunched")
                se.assert_called_once()
                # runas verb used
                self.assertTrue(elev.should_exit_after_elevation(st))

    def test_elevate_uac_cancelled(self):
        with mock.patch.object(elev, "is_admin", return_value=False), mock.patch.object(
            elev, "launch_argv_for_elevation", return_value=(r"C:\x\app.exe", "")
        ), mock.patch.object(elev, "_shell_execute_runas", return_value=-1223):
            os.environ.pop("RPT_NO_AUTO_ELEVATE", None)
            st = elev.elevate_if_needed()
            self.assertEqual(st, "failed:uac_cancelled")
            self.assertFalse(elev.should_exit_after_elevation(st))

    def test_app_main_wires_elevation(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("elevate_if_needed", src)
        self.assertIn("should_exit_after_elevation", src)

    def test_installer_marks_shortcut_runas(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("0x20", src)
        self.assertIn("ReadAllBytes", src)


if __name__ == "__main__":
    unittest.main()
