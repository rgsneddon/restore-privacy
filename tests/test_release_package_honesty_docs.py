"""Docs honesty for catalog monopin package seals (native vs CF).

Skeptic bar: RELEASE notes must not claim native Apple DevID/notarize or
CFBundle monopin 0.5.0 as shipped truth when the paid zip is honest CF.
Also require Windows/Linux native and Android CF wording on this pin.
"""

from __future__ import annotations

import re
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = "0.5.0"


class TestReleasePackageHonestyDocs(unittest.TestCase):
    def _text(self, *parts: str) -> str:
        p = ROOT.joinpath(*parts)
        self.assertTrue(p.is_file(), f"missing {p}")
        return p.read_text(encoding="utf-8")

    def test_release_md_platform_table_native_vs_cf(self):
        t = self._text("scripts", "RELEASE.md")
        self.assertIn("0.5.0", t)
        # Windows + Linux native on this ship
        self.assertRegex(t, r"Windows.*Native|Native.*Windows", re.I | re.S)
        self.assertRegex(t, r"Linux.*Native|Native.*Linux", re.I | re.S)
        # Android CF
        self.assertRegex(t, r"Android.*[Cc]arry-forward|Android.*\bCF\b", re.I | re.S)
        # Apple CF honesty (must not only say notarized as current ship truth)
        self.assertRegex(
            t,
            r"macOS.*[Cc]arry-forward|macOS.*honest CF|macOS.*Honest carry-forward",
            re.I | re.S,
        )
        self.assertRegex(
            t,
            r"iOS.*[Cc]arry-forward|iOS.*honest CF|iOS.*Honest carry-forward",
            re.I | re.S,
        )
        # Must not claim unconditional DevID for current CF ship without CF caveat nearby
        # Ban the old false table row pattern
        self.assertNotIn(
            "Windows / Android / Linux | Honest carry-forward from **0.4.10** until native rebuild",
            t,
        )
        # If Developer ID appears, CF caveat must also appear in same doc
        if re.search(r"Developer ID", t, re.I):
            self.assertRegex(t, r"carry-forward|honest CF|Not\*\* Developer ID|until Mac", re.I)

    def test_release_notes_honesty_table(self):
        for rel in (
            ("scripts", "RELEASE_NOTES_0.5.0.md"),
            ("status_page", "public", "RELEASE_NOTES_0.5.0.md"),
        ):
            t = self._text(*rel)
            self.assertIn("Native", t)
            self.assertIn("Windows", t)
            self.assertIn("Linux", t)
            self.assertIn("Carry-forward", t)
            self.assertIn("macOS", t)
            self.assertIn("iOS", t)
            self.assertIn("CFBundleShortVersionString", t)
            self.assertIn("pre-0.5.0", t)
            # Must not claim Apple CF is notarized as the current ship without CF
            self.assertNotRegex(
                t,
                r"(?i)Apple packages\s*\n-\s*macOS:\s*Developer ID \+ notarize when secrets present\s*\n-\s*iOS:\s*Team-signed sideload when secrets present\s*\n-\s*Built from current tree at monopin \*\*0\.5\.0\*\*",
            )

    def test_apple_handoff_documents_cf_not_native_seal(self):
        t = self._text("client_app", "APPLE_HANDOFF_0.5.0.md")
        self.assertIn("Honest carry-forward", t)
        self.assertIn("CFBundleShortVersionString", t)
        self.assertIn("pre-0.5.0", t)
        self.assertIn("not", t.lower())
        # Target native state may be described, but current VPS status must be CF
        self.assertRegex(t, r"VPS \*\*now\*\*|Status on VPS|current paid assets", re.I)

    def test_public_readme_apple_sections_cf(self):
        t = self._text("status_page", "public", "README.md")
        self.assertIn("honest carry-forward", t.lower())
        self.assertIn("0.5.0", t)
        # Ban old unconditional notarized claim for published v0.5.0 zip
        self.assertNotIn(
            "Published **v0.5.0** macOS catalog zips are **Developer ID signed + notarized**",
            t,
        )
        self.assertNotIn(
            "Published **v0.5.0** iOS packages are **Team-signed** sideload zips (not App Store).",
            t,
        )
        self.assertIn("native 0.5.0", t.lower())
        self.assertIn("Android", t)

    def test_staged_macos_cfbundle_pre_monopin_when_present(self):
        """If the paid macOS zip is present, docs must match its CFBundle honesty."""
        zpath = (
            ROOT
            / "releases"
            / VERSION
            / f"restore-privacy-client-{VERSION}-macos.zip"
        )
        if not zpath.is_file():
            zpath = (
                ROOT
                / "status_page"
                / "assets"
                / VERSION
                / f"restore-privacy-client-{VERSION}-macos.zip"
            )
        if not zpath.is_file():
            self.skipTest("staged macOS zip not present in this checkout")
        short = None
        with zipfile.ZipFile(zpath) as zf:
            for name in zf.namelist():
                if name.endswith("Contents/Info.plist") and "PlugIns" not in name:
                    raw = zf.read(name)
                    m = re.search(
                        rb"CFBundleShortVersionString</key>\s*<string>([^<]+)</string>",
                        raw,
                    )
                    if m:
                        short = m.group(1).decode("ascii", "replace")
                        break
        self.assertIsNotNone(short, "CFBundleShortVersionString not found in macOS zip")
        # CF payload is pre-monopin — release docs must say CF / pre-0.5.0
        notes = self._text("scripts", "RELEASE_NOTES_0.5.0.md")
        if short != VERSION:
            self.assertIn("Carry-forward", notes)
            self.assertIn("pre-0.5.0", notes)
            self.assertIn(short, notes)  # e.g. 0.2.3 when that is the CF payload


if __name__ == "__main__":
    unittest.main()
