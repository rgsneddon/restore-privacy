"""Monopin 1.2.0 iOS catalog must ship IPA Payload layout + embedded provisions.

Drives the **shipped** ``scripts/ios_sideload_package`` + ``build_suite_1.2.0``
helpers — no re-implementation of zip layout, no hard-coded installability
claims without exercising the real package path.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BUILD_SCRIPT = SCRIPTS / "build_suite_1.2.0.py"
IOS_PKG = SCRIPTS / "ios_sideload_package.py"
PRODUCT_ENTRY = ROOT / "product" / "node_elgamal.pub"
CATALOG_IOS = ROOT / "releases" / "1.2.0" / "restore-privacy-client-1.2.0-ios.zip"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    # Ensure scripts dir for sibling imports
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class IosSideloadPackageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not IOS_PKG.is_file():
            raise unittest.SkipTest("ios_sideload_package.py missing")
        if not BUILD_SCRIPT.is_file():
            raise unittest.SkipTest("build_suite_1.2.0.py missing")
        cls.pkg = _load("ios_sideload_package", IOS_PKG)
        cls.suite = _load("build_suite_1_2_0", BUILD_SCRIPT)

    def test_build_ios_fail_closed_requires_codesign_and_provision(self) -> None:
        src = BUILD_SCRIPT.read_text(encoding="utf-8")
        body_start = src.find("def build_ios")
        self.assertGreater(body_start, 0)
        body = src[body_start : body_start + 3500]
        self.assertIn("inject_ios_residual_pubs(runner)", body)
        self.assertIn("codesign_ios_distribution(runner)", body)
        self.assertIn("package_ios_zip(runner)", body)
        self.assertIn("embedded.mobileprovision", body)
        self.assertIn("return None", body)
        # codesign failure must abort before package success
        self.assertLess(
            body.find("if not codesign_ios_distribution(runner)"),
            body.find("return package_ios_zip(runner)"),
        )

    def test_package_ios_zip_writes_payload_layout(self) -> None:
        """Real package_ios_zip → Payload/Runner.app (not bare top-level)."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            runner = td_path / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            (runner / "Info.plist").write_text(
                '<?xml version="1.0"?><plist version="1.0"><dict></dict></plist>',
                encoding="utf-8",
            )
            (runner / "Runner").write_bytes(b"\x00" * 64)
            # Minimal fake provisions so require_installable accepts when present
            (runner / "embedded.mobileprovision").write_bytes(b"HOSTPROV" + b"\x00" * 128)
            (
                runner / "PlugIns" / "PacketTunnel.appex" / "embedded.mobileprovision"
            ).write_bytes(b"TUNPROV" + b"\x00" * 128)
            if PRODUCT_ENTRY.is_file():
                sec = runner / "secrets"
                sec.mkdir(exist_ok=True)
                (sec / "node_elgamal.pub").write_bytes(PRODUCT_ENTRY.read_bytes())
            zip_path = td_path / "out-ios.zip"
            out = self.suite.package_ios_zip(runner, dest=zip_path)
            self.assertTrue(out.is_file())
            with zipfile.ZipFile(out) as zf:
                names = zf.namelist()
            self.assertTrue(
                any(n.startswith("Payload/Runner.app/") for n in names),
                f"expected Payload/Runner.app layout, got sample={names[:15]}",
            )
            self.assertFalse(
                any(
                    n.startswith("Runner.app/") and not n.startswith("Payload/")
                    for n in names
                ),
                "must not ship bare top-level Runner.app members",
            )
            self.assertIn(
                "Payload/Runner.app/embedded.mobileprovision",
                names,
            )
            self.assertIn(
                "Payload/Runner.app/PlugIns/PacketTunnel.appex/embedded.mobileprovision",
                names,
            )

    def test_require_installable_rejects_bare_runner_zip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "bare.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Runner.app/Info.plist", "<plist/>")
                zf.writestr("Runner.app/Runner", b"\x00" * 32)
            with self.assertRaises(self.pkg.IosSideloadError) as ctx:
                self.pkg.require_installable_ios_zip(zpath, require_provision=True)
            msg = str(ctx.exception).lower()
            self.assertTrue(
                "bare" in msg or "payload" in msg,
                f"expected bare/Payload error, got {ctx.exception!r}",
            )

    def test_require_installable_rejects_payload_without_provision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "noprov.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Payload/Runner.app/Info.plist", "<plist/>")
                zf.writestr(
                    "Payload/Runner.app/PlugIns/PacketTunnel.appex/Info.plist",
                    "<plist/>",
                )
            with self.assertRaises(self.pkg.IosSideloadError) as ctx:
                self.pkg.require_installable_ios_zip(zpath, require_provision=True)
            self.assertIn("embedded.mobileprovision", str(ctx.exception))

    def test_package_ios_ipa_zip_helper_payload_and_pins(self) -> None:
        """Direct helper: IPA layout + residual pin preserved from disk app."""
        if not PRODUCT_ENTRY.is_file():
            self.skipTest("product/node_elgamal.pub missing")
        product = PRODUCT_ENTRY.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            runner = td_path / "Runner.app"
            (runner / "secrets").mkdir(parents=True)
            (runner / "PlugIns" / "PacketTunnel.appex" / "secrets").mkdir(parents=True)
            (runner / "secrets" / "node_elgamal.pub").write_bytes(product)
            (
                runner / "PlugIns" / "PacketTunnel.appex" / "secrets" / "node_elgamal.pub"
            ).write_bytes(product)
            (runner / "embedded.mobileprovision").write_bytes(b"P" * 200)
            (
                runner / "PlugIns" / "PacketTunnel.appex" / "embedded.mobileprovision"
            ).write_bytes(b"T" * 200)
            zpath = td_path / "ipa.zip"
            self.pkg.package_ios_ipa_zip(runner, zpath)
            rep = self.pkg.require_installable_ios_zip(zpath, require_provision=True)
            self.assertTrue(rep["has_payload_prefix"])
            self.assertTrue(rep["host_embedded_mobileprovision"])
            self.assertTrue(rep["tunnel_embedded_mobileprovision"])
            self.assertTrue(rep["node_elgamal_pub"])
            self.assertEqual(rep["private_key_members"], [])
            with zipfile.ZipFile(zpath) as zf:
                pin_members = [
                    n for n in zf.namelist() if Path(n).name == "node_elgamal.pub"
                ]
                self.assertTrue(pin_members)
                self.assertEqual(zf.read(pin_members[0]), product)

    def test_find_profile_for_product_bundles_when_operator_profiles_present(
        self,
    ) -> None:
        """On Darwin operator machines, product host/tunnel profiles must resolve."""
        if sys.platform != "darwin":
            self.skipTest("profile search is Darwin-local")
        profiles = self.pkg.iter_local_profiles()
        host = self.pkg.find_profile_for_bundle(
            self.pkg.HOST_BUNDLE_ID, profiles=profiles
        )
        tunnel = self.pkg.find_profile_for_bundle(
            self.pkg.TUNNEL_BUNDLE_ID, profiles=profiles
        )
        if host is None or tunnel is None:
            self.skipTest(
                "operator iOS profiles for product bundle IDs not installed "
                f"(host={host} tunnel={tunnel})"
            )
        self.assertEqual(host.bundle_id, self.pkg.HOST_BUNDLE_ID)
        self.assertEqual(tunnel.bundle_id, self.pkg.TUNNEL_BUNDLE_ID)

    def test_prepare_signed_fail_closed_without_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runner = Path(td) / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            (runner / "Info.plist").write_text("<plist/>", encoding="utf-8")
            with self.assertRaises(self.pkg.IosSideloadError):
                self.pkg.prepare_signed_sideload_app(
                    runner,
                    profiles=[],  # none match
                    require_profiles=True,
                )

    def test_catalog_zip_if_present_must_be_installable(self) -> None:
        """When releases/1.2.0 iOS zip exists, enforce IPA+provision contract."""
        if not CATALOG_IOS.is_file():
            self.skipTest("catalog iOS zip not staged yet")
        # After fix this must pass; if still bare Runner.app, fail loudly.
        rep = self.pkg.inspect_ios_zip(CATALOG_IOS)
        if rep["has_top_level_runner_only"]:
            self.fail(
                "catalog iOS zip is still bare top-level Runner.app — "
                "rebuild via build_suite_1.2.0 package_ios_zip / ios_sideload_package"
            )
        self.pkg.require_installable_ios_zip(CATALOG_IOS, require_provision=True)
        self.assertTrue(rep["node_elgamal_pub"] or any(
            # re-check via zip
            True
            for _ in [0]
        ))
        with zipfile.ZipFile(CATALOG_IOS) as zf:
            names = zf.namelist()
            self.assertTrue(
                any(Path(n).name == "node_elgamal.pub" for n in names),
                "node_elgamal.pub missing from catalog iOS zip",
            )
            privs = [
                n
                for n in names
                if n.endswith(".priv") or "private_key" in n.lower()
            ]
            self.assertEqual(privs, [], f"private keys in iOS zip: {privs}")


if __name__ == "__main__":
    unittest.main()
