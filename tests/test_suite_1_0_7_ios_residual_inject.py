"""Suite 1.0.7 iOS build must inject residual pubs before catalog zip.

Drives the **shipped** ``scripts/build_suite_1.0.7`` inject + package path —
no re-implementation of inject, no hard-coded digests (compare to
``product/node_elgamal.pub``).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_suite_1.0.7.py"
PRODUCT_ENTRY = ROOT / "product" / "node_elgamal.pub"


def _load_suite_build():
    spec = importlib.util.spec_from_file_location("build_suite_1_0_7", BUILD_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class Suite107IosResidualInject(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not BUILD_SCRIPT.is_file():
            raise unittest.SkipTest("build_suite_1.0.7.py missing")
        if not PRODUCT_ENTRY.is_file():
            raise unittest.SkipTest("product/node_elgamal.pub missing")
        cls.mod = _load_suite_build()

    def test_build_ios_source_calls_inject_before_package(self) -> None:
        """Contract: build_ios must call inject helper before packaging zip."""
        src = BUILD_SCRIPT.read_text(encoding="utf-8")
        inject_at = src.find("inject_ios_residual_pubs")
        package_at = src.find("package_ios_zip")
        build_ios_at = src.find("def build_ios")
        self.assertGreater(inject_at, 0, "inject_ios_residual_pubs missing from build script")
        self.assertGreater(package_at, 0, "package_ios_zip missing")
        self.assertGreater(build_ios_at, 0)
        # Within build_ios body, inject must appear before package_ios_zip call.
        body = src[build_ios_at : build_ios_at + 2500]
        self.assertIn("inject_ios_residual_pubs(runner)", body)
        self.assertIn("package_ios_zip(runner)", body)
        self.assertLess(
            body.find("inject_ios_residual_pubs(runner)"),
            body.find("package_ios_zip(runner)"),
            "inject must run before catalog zip write",
        )

    def test_inject_ios_residual_pubs_embeds_product_entry_pin(self) -> None:
        """Real inject API embeds product/node_elgamal.pub into Runner.app/secrets."""
        product = PRODUCT_ENTRY.read_bytes()
        self.assertGreaterEqual(len(product), 32)
        with tempfile.TemporaryDirectory() as td:
            runner = Path(td) / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            # Minimal host + appex layout
            (runner / "Info.plist").write_text("{}", encoding="utf-8")
            dest = self.mod.inject_ios_residual_pubs(runner)
            entry = dest / "node_elgamal.pub"
            self.assertTrue(entry.is_file(), f"missing entry pin under {dest}")
            self.assertEqual(
                entry.read_bytes(),
                product,
                "entry pin bytes must match product/node_elgamal.pub",
            )
            # Appex path also gets secrets (Packet Tunnel load path)
            ape = runner / "PlugIns" / "PacketTunnel.appex" / "secrets" / "node_elgamal.pub"
            self.assertTrue(ape.is_file(), "PacketTunnel.appex must receive entry pin")
            self.assertEqual(ape.read_bytes(), product)

    def test_package_ios_zip_preserves_entry_pin(self) -> None:
        """Zip after inject still contains Runner.app/secrets/node_elgamal.pub."""
        product = PRODUCT_ENTRY.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            runner = td_path / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            (runner / "Info.plist").write_text("{}", encoding="utf-8")
            self.mod.inject_ios_residual_pubs(runner)
            zip_path = td_path / "out-ios.zip"
            self.mod.package_ios_zip(runner, dest=zip_path)
            self.assertTrue(zip_path.is_file())
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                # Basename must be exactly node_elgamal.pub (not de_/us_/exit_*).
                pin_members = [
                    n
                    for n in names
                    if Path(n).name == "node_elgamal.pub"
                ]
                self.assertTrue(pin_members, f"no entry pin in zip; members={names[:20]}")
                data = zf.read(pin_members[0])
                self.assertEqual(data, product)


if __name__ == "__main__":
    unittest.main()
