"""RxShell multi-language CLI + rpOS 0.2.0 packaging surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class TestRxShellRunner(unittest.TestCase):
    def test_python_snippet(self) -> None:
        from rpos.rxshell.runner import run_snippet

        r = run_snippet("print(2+2)", language="python")
        self.assertTrue(r.ok, r.to_dict())
        self.assertEqual(r.language, "python")
        self.assertEqual(r.exit_code, 0)
        self.assertIn("4", r.stdout)

    def test_shell_snippet(self) -> None:
        from rpos.rxshell.runner import run_snippet

        r = run_snippet("echo rxshell-ok", language="shell")
        self.assertTrue(r.ok, r.to_dict())
        self.assertIn("rxshell-ok", r.stdout)

    def test_javascript_or_missing_runtime(self) -> None:
        from rpos.rxshell.runner import run_snippet

        r = run_snippet("console.log(1+1)", language="javascript")
        if r.missing_runtime:
            self.assertFalse(r.ok)
            self.assertEqual(r.exit_code, 127)
            self.assertIn("no host runtime", r.error.lower())
        else:
            self.assertTrue(r.ok, r.to_dict())
            self.assertIn("2", r.stdout)

    def test_powershell_or_missing_runtime(self) -> None:
        from rpos.rxshell.runner import run_snippet

        r = run_snippet("Write-Output 'ps-ok'", language="powershell")
        if r.missing_runtime:
            self.assertFalse(r.ok)
            self.assertTrue(r.missing_runtime)
            self.assertIn("runtime", r.error.lower())
        else:
            self.assertTrue(r.ok, r.to_dict())
            self.assertIn("ps-ok", r.stdout)

    def test_unknown_language_fail_closed(self) -> None:
        from rpos.rxshell.runner import run_snippet

        r = run_snippet("print(1)", language="cobol")
        self.assertFalse(r.ok)
        self.assertEqual(r.exit_code, 127)
        self.assertIn("unsupported language", r.error.lower())
        self.assertNotIn("success", r.error.lower())

    def test_detect_python(self) -> None:
        from rpos.rxshell.runner import detect_language, run_snippet

        self.assertEqual(detect_language("print('x')"), "python")
        r = run_snippet("print('auto')")  # auto-detect
        self.assertTrue(r.ok, r.to_dict())
        self.assertEqual(r.language, "python")
        self.assertIn("auto", r.stdout)

    def test_list_languages(self) -> None:
        from rpos.rxshell.runner import SUPPORTED_LANGUAGES, list_languages

        rows = list_languages()
        ids = {r["language"] for r in rows}
        self.assertEqual(ids, set(SUPPORTED_LANGUAGES))
        # Python must be available when tests run under Python
        py = next(r for r in rows if r["language"] == "python")
        self.assertTrue(py["available"])


class TestRxShellCLI(unittest.TestCase):
    def test_module_version_and_commands(self) -> None:
        env = {**dict(**__import__("os").environ), "PYTHONPATH": str(ROOT)}
        # Launch 1: version
        p1 = subprocess.run(
            [sys.executable, "-m", "rpos.rxshell", "--version"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(p1.returncode, 0, p1.stderr)
        self.assertIn("RxShell", p1.stdout)
        self.assertIn("0.2.0", p1.stdout)
        # Launch 2: multi-language command
        p2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "rpos.rxshell",
                "-c",
                ":python print('cli-ok')",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(p2.returncode, 0, p2.stderr)
        self.assertIn("cli-ok", p2.stdout)
        # Built-in via stdin scripted
        p3 = subprocess.run(
            [sys.executable, "-m", "rpos.rxshell"],
            input="version\n:shell echo shell-ok\nexit\n",
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(p3.returncode, 0, p3.stderr)
        self.assertIn("0.2.0", p3.stdout)
        self.assertIn("shell-ok", p3.stdout)

    def test_repl_run_line_helpers(self) -> None:
        from io import StringIO
        from rpos.rxshell.repl import run_line

        out, err = StringIO(), StringIO()
        rc = run_line("version", out=out, err=err)
        self.assertEqual(rc, 0)
        self.assertIn("RxShell", out.getvalue())
        out2, err2 = StringIO(), StringIO()
        rc2 = run_line(":python print(9*9)", out=out2, err=err2)
        self.assertEqual(rc2, 0)
        self.assertIn("81", out2.getvalue())


class TestRposVersionPackage(unittest.TestCase):
    def test_version_constants_0_2_0(self) -> None:
        import rpos
        from package_rpos import RPOS_VERSION, platform_package_matrix
        from rpos.rxshell import __version__ as rx_ver

        self.assertEqual(rpos.__version__, "0.2.0")
        self.assertEqual(RPOS_VERSION, "0.2.0")
        self.assertEqual(rx_ver, "0.2.0")
        matrix = platform_package_matrix()
        self.assertEqual(len(matrix), 4)
        for slot in matrix:
            self.assertEqual(slot["version"], "0.2.0")
            self.assertIn("0.2.0", slot["archive_name"])
            self.assertNotIn("0.1.0", slot["archive_name"])

    def test_package_one_includes_rxshell(self) -> None:
        from package_rpos import package_one, platform_package_matrix

        slot = next(s for s in platform_package_matrix() if s["platform"] == "macos")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            result = package_one(slot, out_dir=out)
            self.assertTrue(result.get("ok") or result.get("archive"), result)
            archive = Path(result.get("archive") or result.get("path") or "")
            if not archive.is_file():
                # package_one may return different keys
                archives = list(out.glob("*.zip")) + list(out.glob("*.tar.gz"))
                self.assertTrue(archives, result)
                archive = archives[0]
            # Inspect staged content via re-extract or package internals
            import zipfile

            with zipfile.ZipFile(archive, "r") as zf:
                names = zf.namelist()
            joined = "\n".join(names)
            self.assertIn("RxShell", joined)
            self.assertIn("RXSHELL.md", joined)
            self.assertIn("rpos/rxshell/", joined)
            self.assertIn("CAPABILITY.json", joined)
            # CAPABILITY mentions RxShell
            cap_name = next(n for n in names if n.endswith("CAPABILITY.json"))
            with zipfile.ZipFile(archive, "r") as zf:
                cap = json.loads(zf.read(cap_name))
            self.assertEqual(cap.get("version"), "0.2.0")
            self.assertEqual(cap.get("rxshell"), "RxShell")

    def test_brand_inventory_lists_rpos_0_2_0(self) -> None:
        from brand_package_inventory import list_brand_installer_packages

        rows = [
            r
            for r in list_brand_installer_packages(repo_root=ROOT)
            if r.get("kind") == "rpos"
        ]
        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertEqual(r["version"], "0.2.0")
            self.assertIn("0.2.0", r["relative_path"])
            self.assertIn("RxShell", r.get("features") or [])

    def test_architecture_includes_rxshell(self) -> None:
        from architecture_inventory import planned_programs, validate_architecture

        ids = {p["id"] for p in planned_programs()}
        self.assertIn("rxshell", ids)
        self.assertIn("rpos", ids)
        report = validate_architecture(repo_root=ROOT)
        self.assertTrue(report["ok"], report.get("gaps"))


if __name__ == "__main__":
    unittest.main()
