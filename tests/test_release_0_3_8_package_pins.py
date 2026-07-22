"""Catalog 0.3.8 package pins (source monopin + optional staged packages).

Source pins and Apple handoff are always required. Windows multihop PE and
macOS zip are asserted when present under ``releases/0.3.8/`` (gitignored;
operator-built).
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = "0.3.8"
REL = ROOT / "releases" / VERSION
STATUS_ASSETS = ROOT / "status_page" / "assets" / VERSION
WINDOWS = REL / f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
MACOS = REL / f"restore-privacy-client-{VERSION}-macos.zip"
IOS = REL / f"restore-privacy-client-{VERSION}-ios.zip"
STATUS_MACOS = STATUS_ASSETS / f"restore-privacy-client-{VERSION}-macos.zip"
STATUS_IOS = STATUS_ASSETS / f"restore-privacy-client-{VERSION}-ios.zip"
EXIT_PUB_PIN = (
    "a36a3f38066ece7b33abfab6a57942fb998919b4a753ee0d9e9ec9c97c1c7352"
)


class Test038SourcePins(unittest.TestCase):
    def test_client_version_pin(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, VERSION)

    def test_downloads_catalog_pin(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import (
            RELEASE_VERSION,
            RELEASE_TAG,
            MACOS_ZIP_FILENAME,
            IOS_ZIP_FILENAME,
            RELEASE_ASSETS,
            list_catalog_platform_packages,
        )

        self.assertEqual(RELEASE_VERSION, VERSION)
        self.assertEqual(RELEASE_TAG, VERSION)
        self.assertEqual(
            MACOS_ZIP_FILENAME, f"restore-privacy-client-{VERSION}-macos.zip"
        )
        self.assertEqual(
            IOS_ZIP_FILENAME, f"restore-privacy-client-{VERSION}-ios.zip"
        )
        platforms = {a.platform for a in RELEASE_ASSETS}
        self.assertIn("macos", platforms)
        self.assertIn("ios", platforms)
        pkgs = list_catalog_platform_packages()
        names = {p["filename"] for p in pkgs}
        self.assertIn(MACOS_ZIP_FILENAME, names)
        self.assertIn(IOS_ZIP_FILENAME, names)
        # Filenames must embed monopin version for Apple customer packages
        for plat in ("macos", "ios"):
            row = next(p for p in pkgs if p["platform"] == plat)
            self.assertIn(VERSION, row["filename"])
            self.assertEqual(row["version"], VERSION)

    def test_flutter_product_version_pin(self):
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"productVersion = '{VERSION}'", cfg)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertRegex(pub, rf"(?m)^version:\s*{re.escape(VERSION)}\+")

    def test_multihop_routing_implemented(self):
        from client.multihop import MULTI_HOP_ROUTING_IMPLEMENTED, PRODUCT_EXIT_HOST

        self.assertIs(MULTI_HOP_ROUTING_IMPLEMENTED, True)
        self.assertEqual(PRODUCT_EXIT_HOST, "185.146.232.107")

    def test_exit_pub_tracked_and_distinct_from_entry(self):
        exit_p = ROOT / "product" / "exit_node_elgamal.pub"
        entry_p = ROOT / "product" / "node_elgamal.pub"
        self.assertTrue(exit_p.is_file())
        self.assertTrue(entry_p.is_file())
        exit_b = exit_p.read_bytes()
        entry_b = entry_p.read_bytes()
        self.assertGreaterEqual(len(exit_b), 32)
        self.assertNotEqual(exit_b, entry_b)
        self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)

    def test_apple_handoff_present(self):
        h = ROOT / "client_app" / "APPLE_HANDOFF_0.3.8.md"
        self.assertTrue(h.is_file())
        text = h.read_text(encoding="utf-8")
        self.assertIn("0.3.8", text)
        self.assertIn("flutter build macos", text.lower())

    def test_build_release_script_and_release_md(self):
        br = ROOT / "scripts" / f"build_release_{VERSION}.py"
        self.assertTrue(br.is_file())
        src = br.read_text(encoding="utf-8")
        # Real script builds filename from VERSION constant + f-string MACOS_ZIP_NAME
        self.assertIn(f'VERSION = "{VERSION}"', src)
        self.assertIn("restore-privacy-client-{VERSION}-macos.zip", src)
        self.assertIn("MACOS_ZIP_NAME", src)
        self.assertIn("sign_and_notarize_macos", src)
        self.assertIn("_assert_no_priv", src)
        rel = (ROOT / "scripts" / "RELEASE.md").read_text(encoding="utf-8")
        self.assertIn(f"build_release_{VERSION}.py", rel)
        self.assertIn(f"APPLE_HANDOFF_{VERSION}.md", rel)

    def test_readme_catalog_0_3_8(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("0.3.8", text)


@unittest.skipUnless(WINDOWS.is_file(), "releases/0.3.8 Windows PE not present")
class Test038WindowsPeOptional(unittest.TestCase):
    def test_windows_pe_built(self):
        self.assertTrue(WINDOWS.is_file(), f"missing {WINDOWS}")
        self.assertGreater(WINDOWS.stat().st_size, 1_000_000)


@unittest.skipUnless(MACOS.is_file(), "releases/0.3.8 macOS zip not present")
class Test038MacosPackage(unittest.TestCase):
    def test_macos_zip_size_and_no_priv(self):
        self.assertGreater(MACOS.stat().st_size, 1_000_000)
        with zipfile.ZipFile(MACOS) as z:
            names = z.namelist()
            privs = [n for n in names if n.endswith(".priv")]
            self.assertEqual(privs, [], f"private keys in macOS zip: {privs}")
            self.assertTrue(
                any(n.endswith("restore_privacy_client.app/") or n.endswith(".app/") for n in names)
                or any(".app/" in n for n in names),
                "expected .app payload in macOS zip",
            )

    def test_macos_zip_ships_entry_and_exit_pubs(self):
        with zipfile.ZipFile(MACOS) as z:
            exit_names = [n for n in z.namelist() if n.endswith("exit_node_elgamal.pub")]
            entry_names = [
                n
                for n in z.namelist()
                if n.endswith("node_elgamal.pub") and "exit_node" not in n
            ]
            self.assertTrue(exit_names, "exit_node_elgamal.pub missing from macOS zip")
            self.assertTrue(entry_names, "node_elgamal.pub missing from macOS zip")
            exit_b = z.read(exit_names[0])
            self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)
            # Product inject must not ship private material alongside pubs
            secrets_dirs = {
                str(Path(n).parent) for n in exit_names + entry_names
            }
            for d in secrets_dirs:
                for n in z.namelist():
                    if n.startswith(d) and n.endswith(".priv"):
                        self.fail(f"priv next to pubs in zip: {n}")

    def test_macos_cfbundle_version_is_0_3_8(self):
        with zipfile.ZipFile(MACOS) as z:
            # Host app only — skip nested frameworks/plugins/appex
            host = [
                n
                for n in z.namelist()
                if n.endswith("restore_privacy_client.app/Contents/Info.plist")
            ]
            self.assertTrue(host, "host Info.plist missing from macOS zip")
            raw = z.read(host[0])
            # CFBundleShortVersionString marketing version
            self.assertIn(
                VERSION.encode(),
                raw,
                "host Info.plist must pin catalog version 0.3.8",
            )


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(IOS.is_file(), "releases/0.3.8 iOS zip not present")
class Test038IosPackage(unittest.TestCase):
    def test_ios_zip_size_and_no_priv(self):
        self.assertGreater(IOS.stat().st_size, 1_000_000)
        with zipfile.ZipFile(IOS) as z:
            privs = [n for n in z.namelist() if n.endswith(".priv")]
            self.assertEqual(privs, [], f"private keys in iOS zip: {privs}")
            self.assertTrue(
                any("Runner.app" in n for n in z.namelist()),
                "expected Runner.app payload in iOS zip",
            )

    def test_ios_zip_ships_entry_and_exit_pubs(self):
        with zipfile.ZipFile(IOS) as z:
            exit_names = [n for n in z.namelist() if n.endswith("exit_node_elgamal.pub")]
            entry_names = [
                n
                for n in z.namelist()
                if n.endswith("node_elgamal.pub") and "exit_node" not in n
            ]
            self.assertTrue(exit_names, "exit_node_elgamal.pub missing from iOS zip")
            self.assertTrue(entry_names, "node_elgamal.pub missing from iOS zip")
            exit_b = z.read(exit_names[0])
            self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)

    def test_ios_cfbundle_version_is_0_3_8(self):
        with zipfile.ZipFile(IOS) as z:
            host = [
                n
                for n in z.namelist()
                if n == "Runner.app/Info.plist" or n.endswith("Runner.app/Info.plist")
            ]
            self.assertTrue(host, "Runner.app Info.plist missing")
            raw = z.read(host[0])
            self.assertIn(VERSION.encode(), raw)


@unittest.skipUnless(
    STATUS_MACOS.is_file() and STATUS_IOS.is_file(),
    "status_page/assets/0.3.8 Apple zips not staged",
)
class Test038StatusAppleStage(unittest.TestCase):
    def test_staged_apple_match_releases_sizes(self):
        self.assertGreater(STATUS_MACOS.stat().st_size, 1_000_000)
        self.assertGreater(STATUS_IOS.stat().st_size, 1_000_000)
        if MACOS.is_file():
            self.assertEqual(STATUS_MACOS.stat().st_size, MACOS.stat().st_size)
        if IOS.is_file():
            self.assertEqual(STATUS_IOS.stat().st_size, IOS.stat().st_size)
        for p in (STATUS_MACOS, STATUS_IOS):
            with zipfile.ZipFile(p) as z:
                privs = [n for n in z.namelist() if n.endswith(".priv")]
                self.assertEqual(privs, [], f"priv in staged {p.name}")

