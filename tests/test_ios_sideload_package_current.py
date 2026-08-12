"""Current monopin iOS catalog: IPA Payload layout + embedded provisions.

Drives shipped ``scripts/ios_sideload_package`` + current ``build_suite_<pin>``
(from ``client/VERSION``). Historical ``build_suite_1.2.0`` contract retained
separately for archive scripts when present.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
IOS_PKG = SCRIPTS / "ios_sideload_package.py"
PRODUCT_ENTRY = ROOT / "product" / "node_elgamal.pub"
PIN = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
BUILD_SCRIPT = SCRIPTS / f"build_suite_{PIN}.py"
CATALOG_IOS = ROOT / "releases" / PIN / f"restore-privacy-client-{PIN}-ios.zip"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class IosSideloadPackageCurrent(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not IOS_PKG.is_file():
            raise unittest.SkipTest("ios_sideload_package.py missing")
        if not BUILD_SCRIPT.is_file():
            raise unittest.SkipTest(f"{BUILD_SCRIPT.name} missing")
        cls.pkg = _load("ios_sideload_package", IOS_PKG)
        cls.suite = _load(f"build_suite_{PIN.replace('.', '_')}", BUILD_SCRIPT)

    def test_build_ios_fail_closed_requires_codesign_and_provision(self) -> None:
        src = BUILD_SCRIPT.read_text(encoding="utf-8")
        body_start = src.find("def build_ios")
        self.assertGreater(body_start, 0)
        body = src[body_start : body_start + 3500]
        self.assertIn("inject_ios_residual_pubs(runner)", body)
        self.assertIn("codesign_ios_distribution(runner)", body)
        self.assertIn("package_ios_zip(runner)", body)
        self.assertIn("embedded.mobileprovision", body)
        self.assertLess(
            body.find("if not codesign_ios_distribution(runner)"),
            body.find("return package_ios_zip(runner)"),
        )

    def test_package_ios_zip_writes_payload_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            runner = td_path / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            (runner / "Info.plist").write_text(
                '<?xml version="1.0"?><plist version="1.0"><dict></dict></plist>',
                encoding="utf-8",
            )
            (runner / "Runner").write_bytes(b"\x00" * 64)
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
            self.assertTrue(any(n.startswith("Payload/Runner.app/") for n in names))
            self.assertIn("Payload/Runner.app/embedded.mobileprovision", names)

    def test_require_installable_rejects_bare_runner_zip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "bare.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Runner.app/Info.plist", "<plist/>")
            with self.assertRaises(self.pkg.IosSideloadError):
                self.pkg.require_installable_ios_zip(zpath, require_provision=True)

    def test_require_installable_rejects_payload_without_provision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "noprov.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Payload/Runner.app/Info.plist", "<plist/>")
            with self.assertRaises(self.pkg.IosSideloadError):
                self.pkg.require_installable_ios_zip(zpath, require_provision=True)

    def test_prepare_signed_fail_closed_without_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runner = Path(td) / "Runner.app"
            (runner / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            (runner / "Info.plist").write_text("<plist/>", encoding="utf-8")
            with self.assertRaises(self.pkg.IosSideloadError):
                self.pkg.prepare_signed_sideload_app(
                    runner, profiles=[], require_profiles=True
                )

    def test_catalog_zip_if_present_must_be_installable(self) -> None:
        if not CATALOG_IOS.is_file():
            self.skipTest(f"catalog iOS zip not staged yet: {CATALOG_IOS}")
        rep = self.pkg.inspect_ios_zip(CATALOG_IOS)
        if rep["has_top_level_runner_only"]:
            self.fail("catalog iOS zip is bare top-level Runner.app")
        self.pkg.require_installable_ios_zip(CATALOG_IOS, require_provision=True)
        with zipfile.ZipFile(CATALOG_IOS) as zf:
            names = zf.namelist()
            self.assertTrue(any(Path(n).name == "node_elgamal.pub" for n in names))
            privs = [n for n in names if n.endswith(".priv")]
            self.assertEqual(privs, [])


if __name__ == "__main__":
    unittest.main()
