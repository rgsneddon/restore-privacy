"""Windows installer residual spawns must hide consoles (structural)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestInstallerSilentSpawns(unittest.TestCase):
    def test_installer_uses_create_no_window(self) -> None:
        src = (ROOT / "client" / "windows" / "installer.py").read_text(
            encoding="utf-8"
        )
        # Robocopy + PowerShell shortcut + post-install launch
        self.assertIn("CREATE_NO_WINDOW", src)
        self.assertIn("0x08000000", src)
        self.assertIn("-WindowStyle", src)
        self.assertIn("Hidden", src)
        self.assertIn("STARTF_USESHOWWINDOW", src)

    def test_hidden_subprocess_helper_exports(self) -> None:
        from client.windows.hidden_subprocess import (
            CREATE_NO_WINDOW,
            run_hidden,
            residual_shell_run,
            windows_hidden_popen_kwargs,
        )

        self.assertEqual(CREATE_NO_WINDOW, 0x08000000)
        kw = windows_hidden_popen_kwargs()
        if sys.platform == "win32":
            self.assertEqual(kw.get("creationflags"), CREATE_NO_WINDOW)
        self.assertTrue(callable(run_hidden))
        self.assertTrue(callable(residual_shell_run))

    def test_restore_internet_bat_template_hidden_ps(self) -> None:
        src = (ROOT / "client" / "windows" / "installer.py").read_text(
            encoding="utf-8"
        )
        # Failsafe elevation / net restore PowerShell is WindowStyle Hidden
        self.assertGreaterEqual(src.count("-WindowStyle Hidden"), 2)


if __name__ == "__main__":
    unittest.main()
