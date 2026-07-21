"""restore-privacy 0.2.3 is a signed, published GitHub Release (not prep-only).

Public product catalog may also point at RUST-IN-PRIVACY; this test guards the
0.2.3 tag/assets/docs integrity and signing honesty for that version.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.3"
RELEASE_DIR = ROOT / "releases" / VERSION
MACOS_ZIP = RELEASE_DIR / f"restore-privacy-client-{VERSION}-macos.zip"
IOS_ZIP = RELEASE_DIR / f"restore-privacy-client-{VERSION}-ios.zip"


class Test023DocsAndNotesSigned(unittest.TestCase):
    def test_handoff_and_release_notes_signed_not_prep_only(self):
        handoff = ROOT / "client_app" / "APPLE_HANDOFF_0.2.3.md"
        notes = ROOT / "scripts" / "RELEASE_NOTES_0.2.3.md"
        self.assertTrue(handoff.is_file(), "missing APPLE_HANDOFF_0.2.3.md")
        self.assertTrue(notes.is_file(), "missing RELEASE_NOTES_0.2.3.md")
        h = handoff.read_text(encoding="utf-8").lower()
        n = notes.read_text(encoding="utf-8").lower()
        self.assertIn("0.2.3", h)
        self.assertIn("developer id", h)
        self.assertIn("notariz", h)
        self.assertIn("team-signed", h)
        self.assertIn("public package status", h)
        self.assertNotIn("prep packages only", h)
        # Must not claim public 0.2.3 Apple is prep-only sole story
        self.assertIn("do not treat 0.2.3 public apple assets as prep-only", h)
        self.assertIn("developer id signed + notarized", n)
        self.assertIn("team-signed sideload", n)
        self.assertIn("82.221.101.241", n)

    def test_build_release_0_2_3_sign_path_if_present(self):
        script = ROOT / "scripts" / "build_release_0.2.3.py"
        if not script.is_file():
            self.skipTest("build_release_0.2.3.py not in this tree")
        text = script.read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.2.3"', text)
        self.assertIn("sign_and_notarize_macos", text)
        self.assertIn("inject_apple_secrets", text)

    def test_readme_mentions_0_2_3_without_prep_only_current(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        if "0.2.3" not in readme:
            self.skipTest("README does not mention 0.2.3")
        self.assertNotIn("prep packages only", readme)
        # If it still catalogs 0.2.3 macOS as primary packages, require notarize language nearby
        if "restore-privacy-client-0.2.3-macos.zip" in readme:
            self.assertIn("notariz", readme)
            self.assertIn("team-signed", readme)


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
            apps = list((tdp / "mac").rglob("*.app"))
            self.assertTrue(apps)
            app = apps[0]
            out = subprocess.check_output(
                ["codesign", "-dv", "--verbose=2", str(app)],
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertIn("Developer ID Application: Russell Sneddon (SFCBP95595)", out)
            self.assertNotIn("Signature=adhoc", out)
            r = subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(app)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
