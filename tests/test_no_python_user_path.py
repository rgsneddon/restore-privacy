"""Product Windows path without system Python vs source launch that needs Python.

End users install the frozen setup.exe (PyInstaller bundled runtime). Developers
running ``python -m client.windows`` need a host interpreter.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestProductPathNoSystemPython(unittest.TestCase):
    def test_readme_states_no_separate_python_for_windows_installer(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("no separate Python install", text)
        self.assertIn("windows-x64-setup.exe", text.lower())
        # Installer package name advertised
        self.assertIn("restore-privacy-client-", text)

    def test_status_page_notes_no_separate_python(self):
        src = (ROOT / "status_page" / "downloads.py").read_text(encoding="utf-8")
        self.assertIn("WINDOWS_EXE_FILENAME", src)
        self.assertIn("windows-x64-setup.exe", src)
        self.assertIn("no separate Python install", src)

    def test_installer_is_frozen_payload_deployer(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("PyInstaller", src)
        self.assertIn("_MEIPASS", src)
        self.assertIn("getattr(sys, \"frozen\"", src)
        self.assertIn("INSTALL_DIR", src)
        # Deploys bundled client exe â€” not system python -m
        self.assertIn("_find_client_exe", src)
        self.assertNotIn("python -m client.windows", src)

    def test_elevate_frozen_relaunches_bundled_exe(self):
        src = (ROOT / "client" / "windows" / "elevate.py").read_text(encoding="utf-8")
        # Frozen branch must re-launch sys.executable (the .exe), not python.exe
        self.assertIn('getattr(sys, "frozen", False)', src)
        elev = src[src.index("def launch_argv_for_elevation") :]
        frozen_block = elev[: elev.index("def subprocess_list2cmdline")]
        self.assertIn("frozen", frozen_block)
        self.assertIn("sys.executable", frozen_block)

    def test_pyinstaller_windowed_onedir_in_release_recipe(self):
        # Proven recipe still used by later build_release scripts
        recipe = ROOT / "scripts" / "build_release_0.0.8.py"
        self.assertTrue(recipe.is_file(), recipe)
        src = recipe.read_text(encoding="utf-8")
        self.assertIn("PyInstaller", src)
        self.assertIn("--windowed", src)
        self.assertIn("--onedir", src)


class TestSourcePathRequiresPython(unittest.TestCase):
    def test_client_readme_source_launch_uses_python_module(self):
        text = (ROOT / "client" / "README.md").read_text(encoding="utf-8")
        self.assertIn("python -m client.windows", text)

    def test_dev_entry_is_python_module_not_standalone_exe(self):
        main = (ROOT / "client" / "windows" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("client.windows", main)
        # Module entry â€” requires a host interpreter to import
        self.assertIn("from client.windows.app import main", main)

    def test_launch_gui_resolves_host_pythonw(self):
        from client.windows.launch_gui import launch_argv_windowed, prefer_windowed_gui_launch

        self.assertTrue(prefer_windowed_gui_launch())
        exe, args, cwd = launch_argv_windowed()
        # Source path always targets -m client.windows on a host interpreter
        self.assertIn("-m", args)
        self.assertIn("client.windows", args)
        self.assertTrue(exe)
        self.assertTrue((Path(cwd) / "client" / "windows").is_dir())


class TestLocalFrozenArtifactOptional(unittest.TestCase):
    def test_release_or_dist_setup_exe_if_present(self):
        candidates = [
            ROOT
            / "releases"
            / "0.1.8"
            / "restore-privacy-client-0.1.8-windows-x64-setup.exe",
            ROOT / "dist" / "RestorePrivacy-Setup-0.1.8.exe",
        ]
        found = [p for p in candidates if p.is_file()]
        if not found:
            self.skipTest("no local frozen setup binary (build not present)")
        for p in found:
            data = p.read_bytes()[:2]
            self.assertEqual(data, b"MZ", f"not a PE executable: {p}")


if __name__ == "__main__":
    unittest.main()
