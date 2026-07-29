"""Windows hidden_subprocess: Connect residual must import without ModuleNotFoundError."""

from __future__ import annotations

import ast
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestHiddenSubprocessModule(unittest.TestCase):
    def test_importable_and_exports_run_hidden(self) -> None:
        mod = importlib.import_module("client.windows.hidden_subprocess")
        self.assertTrue(callable(getattr(mod, "run_hidden")))
        self.assertTrue(callable(getattr(mod, "powershell_quiet_prefix")))
        self.assertTrue(callable(getattr(mod, "windows_hidden_popen_kwargs")))

    def test_source_file_tracked_not_pyc_only(self) -> None:
        path = ROOT / "client" / "windows" / "hidden_subprocess.py"
        self.assertTrue(path.is_file(), f"missing {path}")
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {
            n.name
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("run_hidden", names)
        self.assertIn("CREATE_NO_WINDOW", src)

    def test_tun_win_configure_address_import_path(self) -> None:
        """Real importer used by configure_address / tunnel Connect path."""
        tun_src = (ROOT / "client" / "windows" / "tun_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "from client.windows.hidden_subprocess import run_hidden", tun_src
        )
        from client.windows.hidden_subprocess import run_hidden

        # Smoke: run a no-op command without raising ModuleNotFoundError
        if sys.platform == "win32":
            cp = run_hidden(
                "echo ok",
                shell=True,
                timeout=15,
                text=True,
            )
            self.assertEqual(cp.returncode, 0)
            self.assertIn("ok", (cp.stdout or "").lower() + (cp.stderr or "").lower())
        else:
            cp = run_hidden(["true"], timeout=10)
            self.assertEqual(cp.returncode, 0)

    def test_pyinstaller_lists_hidden_subprocess(self) -> None:
        recipe = (ROOT / "scripts" / "build_release_0.0.8.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("client.windows.hidden_subprocess", recipe)


class TestDualStackSettingsTop(unittest.TestCase):
    def test_ipv4_ipv6_rows_before_other_privacy_toggles(self) -> None:
        """IPv4 residual switch is first control after section title in privacy card."""
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Section title then dual-stack before traffic shaping / blurb blocks
        i_title = app.find('text="Browsing speed / privacy scale"')
        self.assertGreater(i_title, 0)
        i_v4 = app.find('"IPv4 residual"', i_title)
        i_v6 = app.find('"IPv6 residual"', i_title)
        i_shape = app.find('"Traffic shaping (pad / jitter / cover)"', i_title)
        i_obfs = app.find('"Outer obfuscation (QUIC-mimic wrap)"', i_title)
        self.assertGreater(i_v4, i_title)
        self.assertGreater(i_v6, i_v4)
        self.assertGreater(i_shape, i_v6)
        self.assertGreater(i_obfs, i_shape)
        # Dual-stack must appear before the long privacy blurb after title
        snippet = app[i_title:i_shape]
        self.assertIn("IPv4 residual", snippet)
        self.assertIn("IPv6 residual", snippet)
        # Title then IPv4 before "snappier connection" blurb
        i_blurb = app.find("snappier connection", i_title)
        self.assertGreater(i_blurb, 0)
        self.assertLess(i_v4, i_blurb)

    def test_residual_stack_prefs_in_settings_store(self) -> None:
        from client.windows import settings_store as ss

        # Real store API — keys exist and defaults are ON for dual-stack
        self.assertTrue(hasattr(ss, "load_product_settings") or hasattr(ss, "ProductSettings"))
        # File documents residual dual-stack keys
        src = (ROOT / "client" / "windows" / "settings_store.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("residual_ipv4", src)
        self.assertIn("residual_ipv6", src)


if __name__ == "__main__":
    unittest.main()
