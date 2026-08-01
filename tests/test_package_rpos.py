"""Tests for desktop-only rpOS packaging (Windows / macOS / Linux arches)."""

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


class TestRposMatrix(unittest.TestCase):
    def test_desktop_only_matrix(self) -> None:
        from package_rpos import (
            RPOS_VERSION,
            catalog_platforms,
            excluded_mobile_platforms,
            linux_arches,
            platform_package_matrix,
        )

        self.assertEqual(RPOS_VERSION, "0.1.0")
        plats = catalog_platforms()
        self.assertEqual(
            plats, ["windows", "macos", "linux-x86_64", "linux-aarch64"]
        )
        self.assertEqual(set(linux_arches()), {"x86_64", "aarch64"})
        self.assertEqual(excluded_mobile_platforms(), ["ios", "android"])
        for mobile in ("ios", "android"):
            self.assertNotIn(mobile, plats)
        for s in platform_package_matrix():
            self.assertTrue(s["installable"])
            self.assertFalse(s["mobile"])
            self.assertIn(s["os"], ("windows", "macos", "linux"))


class TestRposPackage(unittest.TestCase):
    def test_package_all_archives(self) -> None:
        from package_rpos import package_all

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "rpos" / "0.1.0"
            r = package_all(version="0.1.0", out_dir=out)
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(r["package_count"], 4)
            self.assertEqual(r["excluded_mobile"], ["ios", "android"])
            man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(man["ok"])
            sums = json.loads((out / "SHA256SUMS.json").read_text(encoding="utf-8"))
            self.assertEqual(len(sums), 4)
            for pkg in man["packages"]:
                arch = Path(pkg["archive"])
                self.assertTrue(arch.is_file(), pkg["archive_name"])
                self.assertGreater(pkg["bytes"], 0)
                self.assertEqual(len(pkg["sha256"]), 64)

    def test_linux_archive_has_install_and_rpos_tree(self) -> None:
        from package_rpos import package_all

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = package_all(
                version="0.1.0", out_dir=out, platforms=["linux-x86_64"]
            )
            self.assertTrue(r.get("ok"), r)
            with tarfile.open(r["packages"][0]["archive"], "r:gz") as tf:
                names = "\n".join(tf.getnames())
                self.assertIn("install.sh", names)
                self.assertIn("RESTORE_rpos.sh", names)
                self.assertIn("CAPABILITY.json", names)
                self.assertIn("rpos/README.md", names)
                self.assertIn("rpos/sdk/", names)
                self.assertIn("bin/rpos-install", names)
                cap = next(n for n in tf.getnames() if n.endswith("CAPABILITY.json"))
                raw = tf.extractfile(cap)
                assert raw is not None
                data = json.loads(raw.read().decode())
                self.assertTrue(data["installable"])
                self.assertFalse(data["mobile"])
                self.assertIn("ios", data["excluded_mobile"])

    def test_windows_and_macos_zips(self) -> None:
        from package_rpos import package_all

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = package_all(
                version="0.1.0",
                out_dir=out,
                platforms=["windows", "macos"],
            )
            self.assertTrue(r.get("ok"), r)
            by = {p["platform"]: p for p in r["packages"]}
            with zipfile.ZipFile(by["windows"]["archive"]) as zf:
                joined = "\n".join(zf.namelist())
                self.assertIn("install.ps1", joined)
                self.assertIn("RESTORE_rpos.ps1", joined)
                self.assertIn("rpos/", joined)
            with zipfile.ZipFile(by["macos"]["archive"]) as zf:
                joined = "\n".join(zf.namelist())
                self.assertIn("install.sh", joined)
                self.assertIn("RESTORE_rpos.sh", joined)

    def test_cli_inventory(self) -> None:
        from package_rpos import main

        self.assertEqual(main(["--inventory"]), 0)


if __name__ == "__main__":
    unittest.main()
