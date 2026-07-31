"""Tests for multi-platform residual node installer packaging.

Drives the real ``scripts/package_node_installers`` entry: pure matrix inventory
and full archive builds for Windows/macOS/Linux/Android/iOS.
"""

from __future__ import annotations

import json
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class TestNodeInstallerMatrix(unittest.TestCase):
    def test_matrix_covers_all_product_platforms(self) -> None:
        from package_node_installers import (
            NODE_INSTALLER_VERSION,
            catalog_platforms,
            platform_package_matrix,
        )

        self.assertEqual(NODE_INSTALLER_VERSION, "1.0.0")
        platforms = catalog_platforms()
        self.assertEqual(
            platforms,
            ["linux", "macos", "windows", "android", "ios"],
        )
        matrix = platform_package_matrix()
        self.assertEqual(len(matrix), 5)
        by_plat = {s["platform"]: s for s in matrix}

        # Linux is residual-capable; others honest lab/reference
        self.assertTrue(by_plat["linux"]["residual_capable"])
        self.assertEqual(by_plat["linux"]["capability"], "residual")
        self.assertEqual(by_plat["linux"]["install_entry"], "install.sh")
        self.assertTrue(by_plat["linux"]["archive_name"].endswith(".tar.gz"))
        self.assertIn("linux", by_plat["linux"]["archive_name"])

        for p in ("macos", "windows", "android", "ios"):
            self.assertFalse(by_plat[p]["residual_capable"], p)
            self.assertIn(by_plat[p]["capability"], ("lab", "lab_reference"))
            self.assertTrue(by_plat[p]["archive_name"].endswith(".zip"), p)
            honesty = by_plat[p]["honesty"].lower()
            self.assertTrue(
                "linux" in honesty or "cannot" in honesty or "lab" in honesty,
                msg=f"{p} honesty must state limits: {honesty[:80]}",
            )

        # Desktop lab gets operator; mobile reference does not
        self.assertTrue(by_plat["macos"]["includes_node_operator"])
        self.assertTrue(by_plat["windows"]["includes_node_operator"])
        self.assertFalse(by_plat["android"]["includes_node_operator"])
        self.assertFalse(by_plat["ios"]["includes_node_operator"])

        # Monopin version on every slot
        for s in matrix:
            self.assertEqual(s["version"], "1.0.0")
            self.assertTrue(s["includes_node_tree"])
            self.assertIn("1.0.0", s["archive_name"])


class TestNodeInstallerPackage(unittest.TestCase):
    def test_package_all_platforms_archives(self) -> None:
        from package_node_installers import package_all_platforms

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "node-installer" / "1.0.0"
            r = package_all_platforms(version="1.0.0", out_dir=out)
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(r["version"], "1.0.0")
            self.assertEqual(
                r["platforms"],
                ["linux", "macos", "windows", "android", "ios"],
            )
            self.assertEqual(r["package_count"], 5)

            man_path = out / "manifest.json"
            self.assertTrue(man_path.is_file())
            man = json.loads(man_path.read_text(encoding="utf-8"))
            self.assertTrue(man["ok"])
            self.assertEqual(len(man["packages"]), 5)

            sums = json.loads((out / "SHA256SUMS.json").read_text(encoding="utf-8"))
            self.assertEqual(len(sums), 5)

            for pkg in man["packages"]:
                arch = Path(pkg["archive"])
                self.assertTrue(arch.is_file(), pkg["archive_name"])
                self.assertGreater(pkg["bytes"], 0)
                self.assertEqual(len(pkg["sha256"]), 64)
                self.assertIn(pkg["archive_name"], sums)
                self.assertEqual(sums[pkg["archive_name"]], pkg["sha256"])

    def test_linux_archive_contains_residual_install_materials(self) -> None:
        from package_node_installers import package_all_platforms

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = package_all_platforms(
                version="1.0.0",
                out_dir=out,
                platforms=["linux"],
            )
            self.assertTrue(r.get("ok"), r)
            arch = Path(r["packages"][0]["archive"])
            with tarfile.open(arch, "r:gz") as tf:
                names = tf.getnames()
                joined = "\n".join(names)
                self.assertIn("install.sh", joined)
                self.assertIn("node/install.sh", joined)
                self.assertIn("node/install_dns.sh", joined)
                self.assertIn("node/install_host_privacy.sh", joined)
                self.assertIn("bin/rpt-node-install", joined)
                self.assertIn("CAPABILITY.md", joined)
                self.assertIn("CAPABILITY.json", joined)
                self.assertIn("NODE_INSTALLER_VERSION", joined)
                self.assertIn("node_operator", joined)
                # Capability claims residual
                cap_member = next(n for n in names if n.endswith("CAPABILITY.json"))
                raw = tf.extractfile(cap_member)
                assert raw is not None
                cap = json.loads(raw.read().decode("utf-8"))
                self.assertTrue(cap["residual_capable"])
                self.assertEqual(cap["capability"], "residual")

    def test_lab_platforms_document_non_residual(self) -> None:
        from package_node_installers import package_all_platforms

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = package_all_platforms(
                version="1.0.0",
                out_dir=out,
                platforms=["macos", "windows", "android", "ios"],
            )
            self.assertTrue(r.get("ok"), r)
            for pkg in r["packages"]:
                self.assertFalse(pkg["residual_capable"], pkg["platform"])
                arch = Path(pkg["archive"])
                with zipfile.ZipFile(arch, "r") as zf:
                    names = zf.namelist()
                    joined = "\n".join(names)
                    self.assertIn("CAPABILITY.json", joined)
                    self.assertIn("node/install.sh", joined)
                    self.assertIn("VERSION", joined)
                    cap_name = next(n for n in names if n.endswith("CAPABILITY.json"))
                    cap = json.loads(zf.read(cap_name).decode("utf-8"))
                    self.assertFalse(cap["residual_capable"])
                    if pkg["platform"] in ("macos", "windows"):
                        self.assertIn("node_operator", joined)
                        self.assertIn("install", joined.lower())
                    if pkg["platform"] == "windows":
                        self.assertIn("install.ps1", joined)
                    if pkg["platform"] == "macos":
                        self.assertIn("install.sh", joined)

    def test_cli_inventory_exit_zero(self) -> None:
        from package_node_installers import main

        # inventory mode prints matrix; exit 0
        code = main(["--inventory"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
