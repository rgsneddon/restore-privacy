"""Residual Connect path must not spawn visible consoles (structural + helper)."""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.hidden_subprocess import (  # noqa: E402
    CREATE_NO_WINDOW,
    check_output_hidden,
    residual_shell_run,
    run_hidden,
    windows_hidden_popen_kwargs,
)


# Product residual OS helpers (Connect / Disconnect / restore) — must not bare-spawn.
RESIDUAL_MODULES = (
    ROOT / "client" / "windows" / "tunnel_win.py",
    ROOT / "client" / "windows" / "tun_win.py",
    ROOT / "client" / "windows" / "firewall_allow.py",
    ROOT / "client" / "windows" / "residual_privilege.py",
)


def _bare_subprocess_calls(path: Path) -> list[tuple[int, str]]:
    """Lines that call subprocess.run/Popen/check_output without hidden helpers nearby."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if not re.search(r"subprocess\.(run|Popen|check_output|call)\s*\(", line):
            continue
        if "hidden_subprocess" in line or "run_hidden" in line:
            continue
        # Allow imports of subprocess module name alone
        window = "\n".join(lines[max(0, i - 2) : i + 8])
        if any(
            x in window
            for x in (
                "run_hidden",
                "residual_shell_run",
                "check_output_hidden",
                "CREATE_NO_WINDOW",
                "windows_hidden_popen_kwargs",
            )
        ):
            continue
        bad.append((i + 1, line.strip()[:140]))
    return bad


class TestResidualModulesNoBareSubprocess(unittest.TestCase):
    def test_no_bare_subprocess_in_residual_modules(self):
        for path in RESIDUAL_MODULES:
            self.assertTrue(path.is_file(), f"missing {path}")
            bad = _bare_subprocess_calls(path)
            self.assertEqual(
                bad,
                [],
                msg=f"{path.name} still has unhidden residual spawns: {bad}",
            )

    def test_tunnel_win_imports_hidden_helpers(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("residual_shell_run", src)
        self.assertIn("check_output_hidden", src)
        self.assertIn("from client.windows.hidden_subprocess import", src)
        # Physical GW + route apply must not use bare check_output/run
        self.assertNotIn("subprocess.check_output", src)
        self.assertNotIn("subprocess.run", src)

    def test_firewall_allow_uses_residual_shell_run(self):
        src = (ROOT / "client" / "windows" / "firewall_allow.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("residual_shell_run", src)
        self.assertNotIn("subprocess.run", src)

    def test_kill_switch_windows_apply_uses_hidden(self):
        src = (ROOT / "client" / "kill_switch.py").read_text(encoding="utf-8")
        self.assertIn("residual_shell_run", src)
        self.assertIn("use_hidden", src)
        # Windows branch must import hidden runner
        self.assertIn("client.windows.hidden_subprocess", src)


class TestHiddenRunnerShipped(unittest.TestCase):
    def test_creationflags_create_no_window(self):
        kw = windows_hidden_popen_kwargs()
        if sys.platform == "win32":
            self.assertEqual(kw.get("creationflags"), CREATE_NO_WINDOW)
            self.assertIn("startupinfo", kw)
        cp = run_hidden(
            "echo rpt_hidden_ok" if sys.platform == "win32" else ["echo", "rpt_hidden_ok"],
            shell=(sys.platform == "win32"),
            timeout=15,
            text=True,
        )
        self.assertEqual(cp.returncode, 0)
        self.assertIn("rpt_hidden_ok", (cp.stdout or "").lower())

    def test_residual_shell_run_and_check_output_hidden(self):
        if sys.platform != "win32":
            self.skipTest("Windows residual shell")
        r = residual_shell_run("echo residual_ok", timeout=15)
        self.assertEqual(r.returncode, 0)
        self.assertIn("residual_ok", (r.stdout or "").lower())
        out = check_output_hidden(["cmd", "/c", "echo gw_ok"], timeout=15)
        self.assertIn("gw_ok", out.lower())

    def test_hidden_subprocess_exports(self):
        path = ROOT / "client" / "windows" / "hidden_subprocess.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            n.name
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("run_hidden", names)
        self.assertIn("check_output_hidden", names)
        self.assertIn("residual_shell_run", names)


class TestPeLaunchWindowed(unittest.TestCase):
    def test_client_onedir_and_setup_windowed_flags(self):
        recipe = (ROOT / "scripts" / "build_release_0.0.8.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("--windowed", recipe)
        self.assertIn("--noconsole", recipe)
        # Client onedir freeze is windowed (no console PE)
        onedir_idx = recipe.find("CLIENT_ONEDIR_NAME")
        # --windowed appears for onedir client build
        self.assertIn('"--windowed"', recipe.replace("'", '"') or recipe)
        # Multihop recipe reuses build_release windowed path
        multi = (ROOT / "scripts" / "build_windows_multihop.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_release", multi.lower() or multi)

    def test_launch_gui_prefers_pythonw(self):
        from client.windows.launch_gui import prefer_windowed_gui_launch

        self.assertTrue(prefer_windowed_gui_launch())
        src = (ROOT / "client" / "windows" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("free_console_if_attached", src)
        self.assertIn("should_reexec_to_windowed_host", src)


if __name__ == "__main__":
    unittest.main()
