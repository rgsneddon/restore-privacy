"""restore-privacy 0.2.3 is the signed, published current public catalog.

README, PRIVACY_POLICY, and status_page/downloads must present 0.2.3 as current
(not RUST-IN-PRIVACY v1.0.0 as the sole public package story). Optional local
zip codesign when releases/0.2.3 Apple packages are on disk.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.3"
RELEASE_DIR = ROOT / "releases" / VERSION
MACOS_ZIP = RELEASE_DIR / f"restore-privacy-client-{VERSION}-macos.zip"
IOS_ZIP = RELEASE_DIR / f"restore-privacy-client-{VERSION}-ios.zip"

sys.path.insert(0, str(ROOT / "status_page"))


class Test023PublicCatalogCurrent(unittest.TestCase):
    def test_readme_current_public_is_0_2_3_signed(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lower = readme.lower()
        self.assertIn("0.2.3", readme)
        self.assertIn("releases/tag/0.2.3", readme)
        self.assertIn("restore-privacy-client-0.2.3-macos.zip", readme)
        self.assertIn("restore-privacy-client-0.2.3-ios.zip", readme)
        self.assertIn("Developer ID", readme)
        self.assertIn("notariz", lower)
        self.assertIn("team-signed", lower)
        self.assertNotIn("prep packages only", lower)
        # Must not present RUST v1.0.0 as the primary Get the app / package table
        self.assertNotIn("Public v1.0.0 (RUST-IN-PRIVACY)", readme)
        self.assertNotIn("restore-privacy-rust-1.0.0-macos.zip", readme)
        self.assertNotIn("legacy private 0.2.3", lower)

    def test_privacy_current_public_is_0_2_3_signed(self):
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("0.2.3", privacy)
        self.assertIn("releases/tag/0.2.3", privacy)
        self.assertIn("Developer ID", privacy)
        self.assertIn("Team-signed", privacy)
        self.assertNotIn(
            "Current public packages:** [RUST-IN-PRIVACY v1.0.0]",
            privacy,
        )

    def test_status_catalog_is_0_2_3_restore_privacy(self):
        from downloads import (  # noqa: E402
            GITHUB_REPO,
            MACOS_ZIP_FILENAME,
            RELEASE_TAG,
            RELEASE_VERSION,
            available_downloads,
        )

        self.assertEqual(RELEASE_VERSION, "0.2.3")
        self.assertEqual(RELEASE_TAG, "0.2.3")
        self.assertEqual(GITHUB_REPO, "restore-privacy")
        self.assertEqual(MACOS_ZIP_FILENAME, "restore-privacy-client-0.2.3-macos.zip")
        names = {a.filename for a in available_downloads()}
        self.assertIn("restore-privacy-client-0.2.3-windows-x64-setup.exe", names)
        self.assertIn("restore-privacy-client-0.2.3-macos.zip", names)
        self.assertIn("restore-privacy-client-0.2.3-ios.zip", names)

    def test_handoff_and_release_notes_signed_not_prep_only(self):
        handoff = ROOT / "client_app" / "APPLE_HANDOFF_0.2.3.md"
        notes = ROOT / "scripts" / "RELEASE_NOTES_0.2.3.md"
        self.assertTrue(handoff.is_file())
        self.assertTrue(notes.is_file())
        h = handoff.read_text(encoding="utf-8").lower()
        n = notes.read_text(encoding="utf-8").lower()
        self.assertIn("public package status", h)
        self.assertIn("developer id", h)
        self.assertIn("notariz", h)
        self.assertIn("team-signed", h)
        self.assertNotIn("prep packages only", h)
        self.assertIn("do not treat 0.2.3 public apple assets as prep-only", h)
        self.assertIn("developer id signed + notarized", n)
        self.assertIn("status page download catalog (catalog **v0.2.3**", n)


class TestLocal023PackagesIfPresent(unittest.TestCase):
    def test_local_zips_no_priv_and_macos_developer_id(self):
        if not MACOS_ZIP.is_file() or not IOS_ZIP.is_file():
            self.skipTest("local releases/0.2.3 Apple zips not present")
        for zpath in (MACOS_ZIP, IOS_ZIP):
            with zipfile.ZipFile(zpath) as zf:
                names = zf.namelist()
                self.assertFalse(any(n.endswith(".priv") for n in names), zpath)
                pubs = [n for n in names if n.endswith("node_elgamal.pub")]
                self.assertTrue(pubs, zpath)
                dig = hashlib.sha256(zf.read(pubs[0])).hexdigest()
                self.assertTrue(dig.startswith("1b126abf"), dig)
        if not shutil.which("codesign"):
            self.skipTest("codesign not available")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            subprocess.run(
                ["unzip", "-q", "-o", str(MACOS_ZIP), "-d", str(tdp / "mac")],
                check=True,
            )
            app = next((tdp / "mac").rglob("*.app"))
            out = subprocess.check_output(
                ["codesign", "-dv", "--verbose=2", str(app)],
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertIn("Developer ID Application: Russell Sneddon (SFCBP95595)", out)
            r = subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(app)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            # Host must not carry restricted NE entitlement under Developer ID
            # (that was the 0.2.3 "can't be opened" / SIGKILL 137 root cause).
            ents = subprocess.check_output(
                ["codesign", "-d", "--entitlements", ":-", str(app)],
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertNotIn(
                "com.apple.developer.networking.networkextension",
                ents,
                "Developer ID host must not claim networkextension",
            )
            self.assertIn("com.apple.security.cs.allow-jit", ents)
            # Appex still carries NE for Packet Tunnel
            appex = next((tdp / "mac").rglob("*.appex"), None)
            if appex is not None:
                aents = subprocess.check_output(
                    ["codesign", "-d", "--entitlements", ":-", str(appex)],
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self.assertIn(
                    "com.apple.developer.networking.networkextension", aents
                )
                self.assertIn("packet-tunnel-provider", aents)


if __name__ == "__main__":
    unittest.main()
