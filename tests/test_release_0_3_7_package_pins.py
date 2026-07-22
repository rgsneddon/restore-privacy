"""Historical catalog 0.3.7 package pins (archived monopin).

Live monopin is 0.3.8+ — do **not** assert client/VERSION or downloads.RELEASE_VERSION
here. This module only checks historical handoff/release artifacts and optional
staged packages under ``releases/0.3.7/`` when present (gitignored).
"""

from __future__ import annotations

import hashlib
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = "0.3.7"
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


class Test037HistoricalArtifacts(unittest.TestCase):
    """Archive-only gates — independent of current monopin."""

    def test_apple_handoff_archive_present(self):
        h = ROOT / "client_app" / "APPLE_HANDOFF_0.3.7.md"
        self.assertTrue(h.is_file())
        text = h.read_text(encoding="utf-8")
        self.assertIn("0.3.7", text)
        self.assertIn("flutter build macos", text.lower())

    def test_build_release_script_archive_present(self):
        br = ROOT / "scripts" / f"build_release_{VERSION}.py"
        self.assertTrue(br.is_file())
        src = br.read_text(encoding="utf-8")
        self.assertIn(f'VERSION = "{VERSION}"', src)
        self.assertIn("restore-privacy-client-{VERSION}-macos.zip", src)
        self.assertIn("sign_and_notarize_macos", src)
        self.assertIn("_assert_no_priv", src)

    def test_release_notes_archive_present(self):
        notes = ROOT / "scripts" / f"RELEASE_NOTES_{VERSION}.md"
        self.assertTrue(notes.is_file())
        text = notes.read_text(encoding="utf-8")
        self.assertIn(VERSION, text)

    def test_multihop_routing_still_implemented(self):
        # Product capability pin (not monopin version)
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


@unittest.skipUnless(WINDOWS.is_file(), "releases/0.3.7 Windows PE not present")
class Test037WindowsPeOptional(unittest.TestCase):
    def test_windows_pe_built(self):
        self.assertTrue(WINDOWS.is_file(), f"missing {WINDOWS}")
        self.assertGreater(WINDOWS.stat().st_size, 1_000_000)


@unittest.skipUnless(MACOS.is_file(), "releases/0.3.7 macOS zip not present")
class Test037MacosPackage(unittest.TestCase):
    def test_macos_zip_size_and_no_priv(self):
        self.assertGreater(MACOS.stat().st_size, 1_000_000)
        with zipfile.ZipFile(MACOS) as z:
            names = z.namelist()
            privs = [n for n in names if n.endswith(".priv")]
            self.assertEqual(privs, [], f"private keys in macOS zip: {privs}")
            self.assertTrue(
                any(".app/" in n for n in names),
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

    def test_macos_cfbundle_version_is_0_3_7(self):
        with zipfile.ZipFile(MACOS) as z:
            host = [
                n
                for n in z.namelist()
                if n.endswith("restore_privacy_client.app/Contents/Info.plist")
            ]
            self.assertTrue(host, "host Info.plist missing from macOS zip")
            raw = z.read(host[0])
            self.assertIn(
                VERSION.encode(),
                raw,
                "host Info.plist must pin catalog version 0.3.7",
            )


@unittest.skipUnless(IOS.is_file(), "releases/0.3.7 iOS zip not present")
class Test037IosPackage(unittest.TestCase):
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

    def test_ios_cfbundle_version_is_0_3_7(self):
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
    "status_page/assets/0.3.7 Apple zips not staged",
)
class Test037StatusAppleStage(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
