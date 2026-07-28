"""Docs honesty for catalog monopin package seals (native CFBundle-aligned macOS).

Paid macOS installer must document CFBundleShortVersionString == monopin when
the staged zip is native; never claim pre-monopin CF as current paid truth.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()


class TestReleasePackageHonestyDocs(unittest.TestCase):
    def _text(self, *parts: str) -> str:
        p = ROOT.joinpath(*parts)
        self.assertTrue(p.is_file(), f"missing {p}")
        return p.read_text(encoding="utf-8")

    def test_apple_handoff_documents_native_cfbundle_monopin(self):
        t = self._text("client_app", f"APPLE_HANDOFF_{VERSION}.md")
        self.assertIn(VERSION, t)
        self.assertIn("CFBundleShortVersionString", t)
        self.assertIn(VERSION, t)
        # Native monopin seal (not pre-monopin CF as current paid truth)
        self.assertRegex(
            t,
            rf"(?i)CFBundleShortVersionString.*\*\*{re.escape(VERSION)}\*\*"
            rf"|CFBundleShortVersionString.*\b{re.escape(VERSION)}\b"
            rf"|\*\*{re.escape(VERSION)}\*\*.*CFBundle",
        )
        self.assertNotIn(f"pre-{VERSION}", t)
        self.assertNotIn("0.2.3", t)

    def test_release_notes_mac_native_monopin(self):
        for rel in (
            ("scripts", f"RELEASE_NOTES_{VERSION}.md"),
            ("status_page", "public", f"RELEASE_NOTES_{VERSION}.md"),
        ):
            p = ROOT.joinpath(*rel)
            if not p.is_file():
                continue
            t = p.read_text(encoding="utf-8")
            self.assertIn(VERSION, t)
            self.assertIn("macOS", t)
            # Must not claim current paid zip is pre-monopin CF
            self.assertNotIn(f"pre-{VERSION}", t)

    def test_readme_macos_not_stale_cfbundle_claim(self):
        for rel in (("README.md",), ("status_page", "public", "README.md")):
            p = ROOT.joinpath(*rel)
            if not p.is_file():
                continue
            t = p.read_text(encoding="utf-8")
            # Ban claiming paid zip CFBundle is still pre-monopin while filename is monopin
            self.assertNotRegex(
                t,
                rf"(?i)CFBundleShortVersionString.*may still be pre-{re.escape(VERSION)}",
            )
            self.assertNotRegex(
                t,
                r"(?i)CFBundle may still be pre-0\.5\.1.*0\.2\.3",
            )

    def test_staged_macos_cfbundle_equals_monopin_when_present(self):
        from apple_package_audit import macos_zip_cfbundle_short_version

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
        short = macos_zip_cfbundle_short_version(zpath)
        self.assertEqual(
            short,
            VERSION,
            f"paid macOS zip CFBundle {short!r} must equal monopin {VERSION}",
        )


if __name__ == "__main__":
    unittest.main()
