"""Docs honesty for catalog monopin package seals (native vs CF).

Skeptic bar: RELEASE notes must not claim native Apple DevID/notarize or
CFBundle monopin 0.5.1 as shipped truth when the paid zip is honest CF.
Also require Windows/Linux native and Android CF wording on this pin.
When the staged macOS zip is present, assert CFBundle is pre-monopin (CF).
"""

from __future__ import annotations

import re
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = "0.5.1"


class TestReleasePackageHonestyDocs(unittest.TestCase):
    def _text(self, *parts: str) -> str:
        p = ROOT.joinpath(*parts)
        self.assertTrue(p.is_file(), f"missing {p}")
        return p.read_text(encoding="utf-8")

    def test_release_md_platform_table_native_vs_cf(self):
        t = self._text("scripts", "RELEASE.md")
        self.assertIn(VERSION, t)
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
        self.assertNotIn(
            "Windows / Android / Linux | Honest carry-forward from **0.4.10** until native rebuild",
            t,
        )
        # If Developer ID appears, CF caveat must also appear in same doc
        if re.search(r"Developer ID", t, re.I):
            self.assertRegex(
                t, r"carry-forward|honest CF|Not\*\* Developer ID|until Mac", re.I
            )

    def test_release_notes_honesty_table(self):
        for rel in (
            ("scripts", f"RELEASE_NOTES_{VERSION}.md"),
            ("status_page", "public", f"RELEASE_NOTES_{VERSION}.md"),
        ):
            t = self._text(*rel)
            self.assertIn("Native", t)
            self.assertIn("Windows", t)
            self.assertIn("Linux", t)
            self.assertIn("Carry-forward", t)
            self.assertIn("macOS", t)
            self.assertIn("iOS", t)
            self.assertIn("CFBundleShortVersionString", t)
            self.assertIn(f"pre-{VERSION}", t)
            # Must not claim Apple CF is notarized as the current ship without CF
            self.assertNotRegex(
                t,
                rf"(?i)Apple packages\s*\n-\s*macOS:\s*Developer ID \+ notarize when secrets present\s*\n-\s*iOS:\s*Team-signed sideload when secrets present\s*\n-\s*Built from current tree at monopin \*\*{re.escape(VERSION)}\*\*",
            )
            # Ban unconditional "native notarized" as current paid truth
            self.assertNotRegex(
                t,
                r"(?i)macOS\s*\|\s*\*\*Native\*\*.*notariz",
            )

    def test_apple_handoff_documents_cf_not_native_seal(self):
        t = self._text("client_app", f"APPLE_HANDOFF_{VERSION}.md")
        self.assertIn("Honest carry-forward", t)
        self.assertIn("CFBundleShortVersionString", t)
        self.assertIn(f"pre-{VERSION}", t)
        self.assertIn("0.2.3", t)
        self.assertIn("not", t.lower())
        # Target native state may be described, but current VPS status must be CF
        self.assertRegex(t, r"VPS \*\*now\*\*|Status on VPS|current paid assets", re.I)
        # Ban claiming current paid zip is native notarized
        self.assertNotRegex(
            t,
            r"(?i)macos\.zip\`\s*\|\s*\*\*Native\*\*.*Developer ID signed \+ notarized",
        )

    def test_public_readme_apple_sections_cf(self):
        t = self._text("status_page", "public", "README.md")
        self.assertIn("honest carry-forward", t.lower())
        self.assertIn(VERSION, t)
        # Ban old unconditional notarized claim for published monopin zip
        self.assertNotIn(
            f"Published **v{VERSION}** macOS catalog zips are **Developer ID signed + notarized**",
            t,
        )
        self.assertNotIn(
            f"Published **v{VERSION}** iOS packages are **Team-signed** sideload zips (not App Store).",
            t,
        )
        self.assertNotIn(
            f"Published **v{VERSION}** macOS catalog zips are a **native** Flutter rebuild",
            t,
        )
        self.assertNotIn(
            f"Published **v{VERSION}** iOS packages are a **native** monopin **{VERSION}**",
            t,
        )
        # Native seals are for Windows/Linux on this pin
        self.assertIn(f"native {VERSION}", t.lower())
        self.assertIn("Android", t)
        self.assertIn("0.2.3", t)

    def test_root_readme_matches_public_apple_honesty(self):
        root = self._text("README.md")
        pub = self._text("status_page", "public", "README.md")
        for t in (root, pub):
            self.assertIn("honest CF", t.lower() + t)
            self.assertRegex(t, r"honest CF|honest carry-forward", re.I)
            self.assertNotRegex(
                t,
                r"(?i)macOS \| `restore-privacy-client-0\.5\.1-macos\.zip` \*\(\*\*native\*\* DevID",
            )

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
            candidates = [
                n
                for n in zf.namelist()
                if n.endswith("Contents/Info.plist")
                and "restore_privacy_client.app/Contents/Info.plist" in n.replace(
                    "\\", "/"
                )
            ]
            if not candidates:
                candidates = [
                    n
                    for n in zf.namelist()
                    if n.replace("\\", "/").endswith(
                        "restore_privacy_client.app/Contents/Info.plist"
                    )
                ]
            self.assertTrue(candidates, "app Info.plist missing in macOS zip")
            raw = zf.read(candidates[0])
            if raw[:6] == b"bplist":
                self.skipTest("binary plist; use text Info.plist for CFBundle probe")
            m = re.search(
                rb"CFBundleShortVersionString.*?<string>([^<]+)</string>",
                raw,
                re.S,
            )
            self.assertIsNotNone(m, "CFBundleShortVersionString not found")
            assert m is not None
            short = m.group(1).decode("utf-8", "replace")
        self.assertIsNotNone(short)
        assert short is not None
        # Paid asset is CF: internal monopin must not equal catalog pin
        self.assertNotEqual(
            short,
            VERSION,
            f"paid macOS zip CFBundle {short!r} claims monopin {VERSION} — "
            "docs must not claim native monopin seal if this is still CF, "
            "or zip must be rebuilt on Mac",
        )
        # Documented honesty must mention pre-monopin / CFBundle / 0.2.3-class
        handoff = self._text("client_app", f"APPLE_HANDOFF_{VERSION}.md")
        self.assertIn("Honest carry-forward", handoff)
        self.assertTrue(
            f"pre-{VERSION}" in handoff or short in handoff,
            "handoff must mention pre-monopin CFBundle honesty",
        )
        notes = self._text("scripts", f"RELEASE_NOTES_{VERSION}.md")
        self.assertIn("Carry-forward", notes)
        self.assertIn(f"pre-{VERSION}", notes)


if __name__ == "__main__":
    unittest.main()
