"""Windows multihop handoff + one-command builder are present and coherent."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestWindowsMultihopHandoff(unittest.TestCase):
    def test_handoff_doc_exists_and_names_single_command(self):
        p = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_0.3.7.md"
        self.assertTrue(p.is_file(), "missing WINDOWS_HANDOFF_0.3.7.md")
        text = p.read_text(encoding="utf-8")
        self.assertIn("build_windows_multihop", text)
        self.assertIn("0.3.7", text)
        self.assertIn("RPT_MULTIHOP_ENABLED", text)
        self.assertIn("exit_node_elgamal.pub", text)
        self.assertIn("185.146.232.107", text)
        self.assertIn("pyinstaller", text.lower())

    def test_builder_script_and_bat_exist(self):
        py = ROOT / "scripts" / "build_windows_multihop.py"
        bat = ROOT / "scripts" / "build_windows_multihop.bat"
        self.assertTrue(py.is_file())
        self.assertTrue(bat.is_file())
        src = py.read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.3.7"', src)
        self.assertIn("rebuild_windows_setup", src)
        self.assertIn("exit_node_elgamal.pub", src)
        self.assertIn("build_release_0.0.8.py", src)
        # Syntax OK
        ast.parse(src)
        bat_text = bat.read_text(encoding="utf-8", errors="replace")
        self.assertIn("build_windows_multihop.py", bat_text)

    def test_recipe_ships_multihop_and_exit_pub(self):
        recipe = (ROOT / "scripts" / "build_release_0.0.8.py").read_text(encoding="utf-8")
        self.assertIn("client.multihop", recipe)
        self.assertIn("exit_node_elgamal.pub", recipe)
        self.assertIn("inject_product_secrets", recipe)

    def test_release_0_3_6_has_windows_only(self):
        src = (ROOT / "scripts" / "build_release_0.3.7.py").read_text(encoding="utf-8")
        self.assertIn("--windows-only", src)
        self.assertIn("build_windows_multihop", src)

    def test_check_only_prereqs_pass_on_this_host(self):
        """--check-only must not require a Windows PE freeze."""
        import importlib.util

        path = ROOT / "scripts" / "build_windows_multihop.py"
        spec = importlib.util.spec_from_file_location("bw_mh_check", path)
        assert spec and spec.loader
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        # May fail if PyInstaller missing — install is optional on mac CI.
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            self.skipTest("PyInstaller not installed on this host")
        rc = m.main(["--check-only"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
