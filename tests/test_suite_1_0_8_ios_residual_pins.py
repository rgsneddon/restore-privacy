"""Suite 1.0.8 iOS package: live residual pins only (no retired US).

Drives the **shipped** inject path and inspects the real staged monopin zip
when present — compares entry pin bytes to ``product/node_elgamal.pub`` (no
hard-coded digests).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_suite_1.0.8.py"
PRODUCT = ROOT / "product"
PRODUCT_ENTRY = PRODUCT / "node_elgamal.pub"
PRODUCT_DE = PRODUCT / "de_node_elgamal.pub"
PRODUCT_EXIT = PRODUCT / "exit_node_elgamal.pub"
VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
STAGED_IOS = ROOT / "releases" / VERSION / f"restore-privacy-client-{VERSION}-ios.zip"


def _load_suite_build():
    spec = importlib.util.spec_from_file_location("build_suite_1_0_8", BUILD_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class Suite108IosResidualPins(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not BUILD_SCRIPT.is_file():
            raise unittest.SkipTest("build_suite_1.0.8.py missing")
        if not PRODUCT_ENTRY.is_file():
            raise unittest.SkipTest("product/node_elgamal.pub missing")
        cls.mod = _load_suite_build()
        cls.entry = PRODUCT_ENTRY.read_bytes()
        cls.de = PRODUCT_DE.read_bytes() if PRODUCT_DE.is_file() else b""
        cls.exit = PRODUCT_EXIT.read_bytes() if PRODUCT_EXIT.is_file() else b""

    def test_build_ios_injects_before_package_and_strips_us(self) -> None:
        src = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("inject_ios_residual_pubs", src)
        self.assertIn("us_node_elgamal.pub", src)  # documents non-inject
        self.assertIn("Does not** inject retired", src.replace("\n", " ") or src)
        body_at = src.find("def build_ios")
        body = src[body_at : body_at + 2800]
        self.assertIn("inject_ios_residual_pubs(runner)", body)
        self.assertIn("package_ios_zip(runner)", body)
        self.assertLess(
            body.find("inject_ios_residual_pubs(runner)"),
            body.find("package_ios_zip(runner)"),
        )

    def test_inject_api_live_pubs_only_no_us(self) -> None:
        """Real inject_ios_residual_pubs: IS+DE+exit match product; US removed."""
        with tempfile.TemporaryDirectory() as td:
            runner = Path(td) / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex" / "secrets").mkdir(
                parents=True
            )
            (runner / "secrets").mkdir(parents=True)
            # Stale US from prior build must be stripped
            (runner / "secrets" / "us_node_elgamal.pub").write_bytes(b"\x00" * 64)
            (
                runner
                / "PlugIns"
                / "PacketTunnel.appex"
                / "secrets"
                / "us_node_elgamal.pub"
            ).write_bytes(b"\x00" * 64)
            (runner / "Info.plist").write_text("{}", encoding="utf-8")
            dest = self.mod.inject_ios_residual_pubs(runner)
            self.assertEqual((dest / "node_elgamal.pub").read_bytes(), self.entry)
            if self.de:
                self.assertEqual((dest / "de_node_elgamal.pub").read_bytes(), self.de)
            if self.exit:
                self.assertEqual(
                    (dest / "exit_node_elgamal.pub").read_bytes(), self.exit
                )
            self.assertFalse((dest / "us_node_elgamal.pub").exists())
            ape = runner / "PlugIns" / "PacketTunnel.appex" / "secrets"
            self.assertEqual((ape / "node_elgamal.pub").read_bytes(), self.entry)
            self.assertFalse((ape / "us_node_elgamal.pub").exists())

    def test_staged_monopin_ios_zip_pin_policy(self) -> None:
        """Staged catalog zip: entry match product; DE+exit present; no US; no priv."""
        if not STAGED_IOS.is_file():
            self.skipTest(f"staged iOS zip missing: {STAGED_IOS}")
        self.assertEqual(
            STAGED_IOS.name, f"restore-privacy-client-{VERSION}-ios.zip"
        )
        with zipfile.ZipFile(STAGED_IOS) as zf:
            names = zf.namelist()
            pubs = [n for n in names if n.endswith(".pub")]
            privs = [n for n in names if n.endswith(".priv")]
            self.assertEqual(privs, [], f"must not embed priv: {privs}")
            us = [n for n in pubs if Path(n).name == "us_node_elgamal.pub"]
            self.assertEqual(us, [], f"retired US pin must not ship: {us}")
            # Entry pin members match product monopin bytes
            entry_members = [n for n in pubs if Path(n).name == "node_elgamal.pub"]
            self.assertTrue(entry_members, "missing node_elgamal.pub in zip")
            for n in entry_members:
                self.assertEqual(
                    zf.read(n),
                    self.entry,
                    f"entry pin mismatch in {n}",
                )
            for base, product in (
                ("de_node_elgamal.pub", self.de),
                ("exit_node_elgamal.pub", self.exit),
            ):
                if not product:
                    continue
                members = [n for n in pubs if Path(n).name == base]
                self.assertTrue(members, f"missing {base}")
                for n in members:
                    self.assertEqual(zf.read(n), product, f"mismatch {n}")
            # Host + PacketTunnel secrets trees both carry live set
            host = {
                Path(n).name
                for n in pubs
                if n.startswith("Runner.app/secrets/")
            }
            ape = {
                Path(n).name
                for n in pubs
                if "PacketTunnel.appex" in n and "/secrets/" in n
            }
            for need in ("node_elgamal.pub", "de_node_elgamal.pub", "exit_node_elgamal.pub"):
                self.assertIn(need, host, host)
                self.assertIn(need, ape, ape)
            self.assertNotIn("us_node_elgamal.pub", host)
            self.assertNotIn("us_node_elgamal.pub", ape)


if __name__ == "__main__":
    unittest.main()
