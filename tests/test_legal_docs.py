"""Tests read shipped privacy policy, LICENSE, CREDITS, and README how-to."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    path = ROOT / name
    assert path.is_file(), f"missing shipped file: {name}"
    text = path.read_text(encoding="utf-8")
    assert len(text) > 200, f"{name} is too short to be a full document"
    return text


class TestPrivacyPolicy(unittest.TestCase):
    def test_policy_exists_and_covers_no_collection_themes(self):
        text = _read("PRIVACY_POLICY.md")
        lower = text.lower()
        self.assertIn("privacy policy", lower)
        # No user-info / session activity logging themes
        self.assertTrue(
            "no user-info" in lower
            or "user-info logs" in lower
            or "session" in lower and "log" in lower
        )
        self.assertIn("not", lower)
        self.assertTrue(
            "connection log" in lower
            or "session log" in lower
            or "traffic log" in lower
            or "activity log" in lower
        )
        # Public page no longer advertises a live client count
        self.assertTrue(
            "no public" in lower
            or "not" in lower
            and ("count" in lower or "session" in lower)
            or "status" in lower
        )
        # Operational limits section
        self.assertTrue("limit" in lower or "limits" in lower)
        # Multi-platform client apps (shipped wording)
        self.assertIn("Windows", text)
        self.assertIn("Android", text)
        self.assertIn("iOS", text)
        self.assertIn("macOS", text)
        self.assertNotIn("iOS/macOS prep", text)
        # Pointers to related docs
        self.assertIn("LICENSE", text)
        self.assertIn("README", text)

    def test_policy_public_catalog_is_v1_0_0(self):
        """User-facing policy must advertise public catalog v1.0.0, not v0.2.3."""
        text = _read("PRIVACY_POLICY.md")
        self.assertIn("v1.0.0", text)
        self.assertIn("RUST-IN-PRIVACY", text)
        self.assertIn("releases/tag/v1.0.0", text)
        self.assertNotIn("current catalog: **v0.2.3**", text)
        # Primary package host line is RUST-IN-PRIVACY, not private 0.2.3 tag as current
        self.assertIn(
            "https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/tag/v1.0.0",
            text,
        )


class TestLicenseAndCredits(unittest.TestCase):
    def test_license_mit_and_third_party_section(self):
        text = _read("LICENSE")
        self.assertIn("MIT License", text)
        self.assertIn("Copyright", text)
        self.assertIn("PERMISSION IS HEREBY GRANTED", text.upper())
        # Credits / third-party acknowledgment in license
        self.assertTrue(
            "THIRD-PARTY" in text.upper() or "Wintun" in text or "CREDITS" in text
        )
        # Apple stack utilised components (aligned with CREDITS.md)
        self.assertIn("CryptoKit", text)
        self.assertIn("BigInt", text)

    def test_credits_name_utilised_components(self):
        text = _read("CREDITS.md")
        # Must credit real utilised parts
        for name in ("Wintun", "cryptography", "Bouncy", "Flutter", "CryptoKit", "BigInt"):
            self.assertIn(name, text, f"missing credit for {name}")
        self.assertIn("wintun", text.lower())
        self.assertIn("not", text.lower())
        # Clarify not WireGuard protocol
        self.assertTrue("wireguard" in text.lower() or "WireGuard" in text)


class TestReadmeHowto(unittest.TestCase):
    def test_readme_howto_and_legal_links(self):
        """Public README: client-user how-to + legal links (operator detail in sundries)."""
        text = _read("README.md")
        lower = text.lower()
        self.assertTrue("how to" in lower or "install" in lower)
        # End-user client path â€” all published platforms
        self.assertIn("download", lower)
        self.assertIn("windows", lower)
        self.assertIn("android", lower)
        self.assertIn("macos", lower)
        self.assertIn("ios", lower)
        # Public ship is RUST-IN-PRIVACY v1.0.0; private tree may still mention 0.2.3 history
        self.assertTrue(
            "1.0.0" in text or "0.2.3" in text or "0.2.1" in text or "0.2.0" in text,
            "README must cite public v1.0.0 and/or historical 0.2.x",
        )
        self.assertIn("RUST-IN-PRIVACY", text)
        self.assertIn("releases/tag/v1.0.0", text)
        self.assertNotIn("prep stubs", lower)
        # Package basenames from the public release catalog
        self.assertTrue(
            "restore-privacy-rust-1.0.0-windows-x64.zip" in text
            or "windows-x64.zip" in text
            or "windows-x64-setup.exe" in text,
            "README must cite a Windows package basename",
        )
        self.assertIn("android.apk", text)
        self.assertIn("macos.zip", text)
        self.assertIn("ios.zip", text)
        # Links / names to legal docs
        self.assertIn("PRIVACY_POLICY", text)
        self.assertIn("LICENSE", text)
        self.assertTrue("CREDITS" in text or "credit" in lower)
        # User-facing status/downloads OK; operator deploy is not required here
        self.assertTrue(
            "restore-privacy-status.onrender.com" in text
            or "status page" in lower
            or "download" in lower
        )
        # Operator material lives in sundries
        self.assertTrue(
            (ROOT / "sundries.txt").is_file()
            or "sundries" in lower
        )


if __name__ == "__main__":
    unittest.main()
