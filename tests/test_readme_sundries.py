"""Tests: public README is client-user focused; sundries holds operator topics."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    path = ROOT / name
    assert path.is_file(), f"missing shipped file: {name}"
    return path.read_text(encoding="utf-8")


class TestSundriesHoldsOperatorTopics(unittest.TestCase):
    def test_sundries_exists_with_relocated_topics(self):
        text = _read("sundries.txt")
        self.assertGreater(len(text), 400)
        lower = text.lower()
        # Ports / node listen
        self.assertTrue("44044" in text or "ports" in lower)
        self.assertTrue("8080" in text or "status ui" in lower)
        # Status page hosting / deploy detail
        self.assertTrue(
            "render" in lower or "status_page" in lower or "onrender" in lower
        )
        # Deploy node
        self.assertTrue(
            "deploy" in lower and ("node" in lower or "install.sh" in lower)
        )
        self.assertIn("RPT_SSH", text)
        # Client apps developer notes
        self.assertTrue(
            "python -m client.windows" in text or "flutter" in lower
        )
        # Local tests
        self.assertTrue("unittest" in lower or "local tests" in lower)
        # Secrets
        self.assertTrue("secrets" in lower and (".priv" in text or "private" in lower))


class TestReadmePublicClientOnly(unittest.TestCase):
    def test_readme_is_end_user_focused(self):
        text = _read("README.md")
        lower = text.lower()
        # End-user how-to
        self.assertTrue("download" in lower or "install" in lower)
        self.assertTrue(
            "restoreprivacy.bat" in lower
            or "run as administrator" in lower
            or "apk" in lower
        )
        self.assertTrue("0.0.1" in text or "release" in lower)
        self.assertIn("PRIVACY_POLICY", text)
        self.assertIn("LICENSE", text)
        self.assertTrue("CREDITS" in text or "credit" in lower)
        # Status page as user surface is OK
        self.assertTrue(
            "restore-privacy-status.onrender.com" in text
            or "status page" in lower
            or "download" in lower
        )
        # Operator deploy / secrets / unittest must NOT be the README focus
        self.assertNotIn("RPT_SSH_PASSWORD", text)
        self.assertNotIn("export RPT_SSH", text)
        self.assertNotIn("unittest discover", text)
        self.assertNotIn("## Secrets", text)
        self.assertNotIn("### 5. Deploy or operate the VPN node", text)
        self.assertNotIn("### 6. Run tests", text)
        # Optional pointer to sundries for operators
        self.assertIn("sundries.txt", text)

    def test_readme_still_usable_how_to(self):
        text = _read("README.md")
        lower = text.lower()
        self.assertTrue("how to" in lower or "install" in lower)
        self.assertTrue("windows" in lower)
        self.assertTrue("android" in lower or "apk" in lower)
        self.assertTrue("macos" in lower)
        self.assertTrue("ios" in lower)
        self.assertIn("0.1.6", text)
        # Not prep-stub-only Apple wording
        self.assertNotIn("prep stubs", lower)


if __name__ == "__main__":
    unittest.main()
