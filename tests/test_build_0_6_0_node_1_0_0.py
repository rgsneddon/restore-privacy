"""Client monopin 0.6.0 basenames + Node Operator 1.0.0 Linux package matrix.

Drives shipped package_node_operator_linux helpers and build_release_0.6.0 names.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _load_build_060():
    path = ROOT / "scripts" / "build_release_0.6.0.py"
    spec = importlib.util.spec_from_file_location("build_release_0_6_0", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestClient060Names(unittest.TestCase):
    def test_build_release_0_6_0_pin_and_basenames(self) -> None:
        mod = _load_build_060()
        self.assertEqual(mod.VERSION, "0.6.0")
        self.assertEqual(
            mod.WINDOWS_EXE_NAME,
            "restore-privacy-client-0.6.0-windows-x64-setup.exe",
        )
        self.assertEqual(
            mod.ANDROID_APK_NAME, "restore-privacy-client-0.6.0-android.apk"
        )
        self.assertEqual(
            mod.MACOS_ZIP_NAME, "restore-privacy-client-0.6.0-macos.zip"
        )
        self.assertEqual(mod.IOS_ZIP_NAME, "restore-privacy-client-0.6.0-ios.zip")
        self.assertEqual(
            mod.LINUX_TGZ_NAME,
            "restore-privacy-client-0.6.0-linux-x64.tar.gz",
        )
        self.assertEqual(mod.OUT, ROOT / "releases" / "0.6.0")


class TestNodeOperator100Linux(unittest.TestCase):
    def test_versionable_matrix_full_product_set(self) -> None:
        import package_linux as pl
        from package_node_operator_linux import (
            NODE_OPERATOR_VERSION,
            linux_versionable_matrix,
        )

        m = linux_versionable_matrix()
        self.assertEqual(NODE_OPERATOR_VERSION, "1.0.0")
        self.assertEqual(m["node_operator_version"], "1.0.0")
        self.assertEqual(tuple(m["python_abi_tags"]), pl._PY_VERSIONS)
        self.assertEqual(tuple(m["platforms"]), pl._PLATFORMS)
        # All pairs: 6 CPython × 3 manylinux tags
        self.assertEqual(m["pair_count"], len(pl._PY_VERSIONS) * len(pl._PLATFORMS))
        self.assertEqual(m["pair_count"], 18)
        self.assertEqual(len(m["pairs"]), 18)

    def test_package_structure_skip_wheels(self) -> None:
        from package_node_operator_linux import package_node_operator_linux

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = package_node_operator_linux(
                version="1.0.0",
                out_dir=out,
                skip_wheels=True,
            )
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(r.get("version"), "1.0.0")
            arch = Path(str(r["archive"]))
            self.assertTrue(arch.is_file())
            self.assertEqual(
                arch.name,
                "restore-privacy-node-operator-1.0.0-linux-x64.tar.gz",
            )
            # Manifest lists full matrix even when wheels skipped
            man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(man["matrix"]["pair_count"], 18)
            self.assertEqual(man["entry"], "python -m node_operator")

    def test_archive_contains_operator_entry(self) -> None:
        import tarfile

        from package_node_operator_linux import package_node_operator_linux

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = package_node_operator_linux(
                version="1.0.0", out_dir=out, skip_wheels=True
            )
            self.assertTrue(r.get("ok"), r)
            with tarfile.open(r["archive"], "r:gz") as tf:
                names = tf.getnames()
            joined = "\n".join(names)
            self.assertIn("node_operator", joined)
            self.assertIn("bin/rpt-node-operator", joined)
            self.assertIn("NODE_OPERATOR_VERSION", joined)
            self.assertIn("WHEEL_MATRIX.json", joined)
            self.assertIn("install.sh", joined)


if __name__ == "__main__":
    unittest.main()
