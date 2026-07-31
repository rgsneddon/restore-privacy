"""Suite redeploy package + perc_chain Helsinki packaging (Restore Privacy Suite v1.0.0)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSuiteRedeployPackage(unittest.TestCase):
    def test_list_catalog_five_platforms_1_0_0(self):
        pkg = _load("package_suite", "scripts/package_restore_privacy_suite.py")
        catalog = pkg.list_catalog("1.0.0")
        self.assertEqual(len(catalog), 5)
        plats = {e["platform"] for e in catalog}
        self.assertEqual(plats, {"windows", "android", "macos", "ios", "linux"})
        for e in catalog:
            self.assertEqual(e["version"], "1.0.0")
            self.assertEqual(e["product"], "Restore Privacy Suite")
            self.assertIn("1.0.0", e["filename"])
            self.assertTrue(e["filename"].startswith("restore-privacy-suite-"))

    def test_build_commands_cover_platforms_and_chain(self):
        pkg = _load("package_suite", "scripts/package_restore_privacy_suite.py")
        cmds = pkg.build_commands("1.0.0")
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(plat, cmds)
            self.assertIn("flutter build", cmds[plat])
        self.assertIn("deploy_perc_chain_helsinki", cmds["perc_chain"])

    def test_stage_dry_run_and_stage_write(self):
        pkg = _load("package_suite", "scripts/package_restore_privacy_suite.py")
        # dry-run path (no writes required beyond function call)
        out = pkg.stage_manifest("1.0.0", dry_run=True)
        self.assertTrue(str(out).endswith("suite_package_manifest.json"))

        # real stage
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "package_restore_privacy_suite.py"),
                "--stage",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        manifest = ROOT / "dist" / "suite" / "1.0.0" / "suite_package_manifest.json"
        self.assertTrue(manifest.is_file(), manifest)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["product"], "Restore Privacy Suite")
        self.assertIn("paused", data["perc_chain"]["paused_note"].lower())

    def test_perc_chain_package_dry_run(self):
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deploy_perc_chain_helsinki.py"),
                "--package",
                "--dry-run",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("135.181.152.10", r.stdout)
        self.assertIn("paused", r.stdout.lower())

    def test_perc_chain_package_tarball(self):
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deploy_perc_chain_helsinki.py"),
                "--package",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        tarball = (
            ROOT
            / "dist"
            / "suite"
            / "1.0.0"
            / "rpt-perc-chain-1.0.0-helsinki.tar.gz"
        )
        self.assertTrue(tarball.is_file(), tarball)
        meta = ROOT / "dist" / "suite" / "1.0.0" / "perc_chain_package.json"
        data = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "1.0.0")
        self.assertNotIn("onrender.com", data["public_endpoint"])

    def test_client_version_and_network_asset(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "1.0.0")
        net = (ROOT / "client_app" / "assets" / "config" / "perc_network.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("135.181.152.10", net)
        self.assertIn("/perc", net)
        self.assertNotIn("evolve-perc-internet.onrender.com", net)
        self.assertIn("paused", net.lower())

    def test_deploy_doc_records_render_pause(self):
        doc = (ROOT / "perc_chain" / "DEPLOY_HELSINKI.md").read_text(encoding="utf-8")
        self.assertIn("paused to save money", doc.lower())
        self.assertIn("135.181.152.10", doc)
        self.assertIn("9478", doc)


if __name__ == "__main__":
    unittest.main()
